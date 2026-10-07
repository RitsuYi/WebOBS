// Temporary, read-only sensor session. No boot-start or permanent user-mode service.
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using Microsoft.Win32.SafeHandles;

internal sealed class PortableSession : IDisposable
{
    public readonly ManualResetEvent Stopped = new ManualResetEvent(false);
    private Process parent;
    private NamedPipeServerStream pipe;
    private StreamWriter writer;
    private EventWaitHandle parentStop;

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool DuplicateHandle(IntPtr sourceProcess, IntPtr sourceHandle, IntPtr targetProcess,
        out IntPtr targetHandle, uint access, bool inherit, uint options);
    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();

    public PortableSession(int parentId, long parentTime, string pipeName, long stopHandle)
    {
        if (!System.Text.RegularExpressions.Regex.IsMatch(pipeName,
            "^WebOBS\\.Sensors\\." + parentId + "\\.[a-f0-9]{32}$"))
            throw new ArgumentException("Invalid sensor session name.");
        parent = Process.GetProcessById(parentId);
        if (parent.StartTime.ToUniversalTime().ToFileTimeUtc() != parentTime || parent.HasExited)
            throw new InvalidOperationException("WebOBS parent has exited or changed.");
        IntPtr duplicated;
        if (!DuplicateHandle(parent.Handle, new IntPtr(stopHandle), GetCurrentProcess(), out duplicated, 0, false, 2))
            throw new Win32Exception();
        parentStop = new EventWaitHandle(false, EventResetMode.ManualReset);
        parentStop.SafeWaitHandle.Dispose();
        parentStop.SafeWaitHandle = new SafeWaitHandle(duplicated, true);
        IntPtr token;
        if (!OpenProcessToken(parent.Handle, 8, out token)) throw new Win32Exception();
        SecurityIdentifier user;
        try { using (var identity = new WindowsIdentity(token)) user = identity.User; }
        finally { CloseHandle(token); }
        var security = new PipeSecurity();
        security.SetAccessRuleProtection(true, false);
        security.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid, null),
            PipeAccessRights.FullControl, AccessControlType.Deny));
        security.AddAccessRule(new PipeAccessRule(user, PipeAccessRights.Read, AccessControlType.Allow));
        security.AddAccessRule(new PipeAccessRule(WindowsIdentity.GetCurrent().User,
            PipeAccessRights.FullControl, AccessControlType.Allow));
        pipe = new NamedPipeServerStream(pipeName, PipeDirection.Out, 1, PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous, 0, 2097152, security);
        ThreadPool.QueueUserWorkItem(delegate {
            while (!Stopped.WaitOne(100))
            {
                if (!parent.HasExited && !parentStop.WaitOne(0)) continue;
                Stopped.Set();
                try { pipe.Dispose(); } catch (ObjectDisposedException) { }
            }
        });
    }

    public void Connect()
    {
        var pending = pipe.BeginWaitForConnection(null, null);
        DateTime deadline = DateTime.UtcNow.AddSeconds(30);
        while (!pending.IsCompleted)
        {
            if (Stopped.WaitOne(100) || DateTime.UtcNow > deadline)
                throw new IOException("Sensor client did not connect.");
        }
        pipe.EndWaitForConnection(pending);
        writer = new StreamWriter(pipe, new UTF8Encoding(false)) { AutoFlush = true };
    }

    public void Write(string packet) { writer.WriteLine(packet); }
    public void Dispose()
    {
        Stopped.Set();
        if (writer != null) writer.Dispose();
        if (pipe != null) pipe.Dispose();
        // The parent handles stay valid until the short-lived watcher finishes.
    }
}

internal sealed class PortableDriver : IDisposable
{
    private const string DriverHash = "f92de04e5a02256e86ffa1b4252fe669282198b7329227f40e51bca9267d133d";
    private IntPtr manager, service;
    private Mutex lease;
    private bool locked;
    private bool started;
    private string directory, file;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct OsVersion
    {
        public uint size, major, minor, build, platform;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string servicePack;
    }
    [DllImport("ntdll.dll", CharSet = CharSet.Unicode)]
    private static extern int RtlGetVersion(ref OsVersion version);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool IsWow64Process2(IntPtr process, out ushort processMachine, out ushort nativeMachine);
    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();

    private static void CheckPlatform()
    {
        var version = new OsVersion { size = (uint)Marshal.SizeOf(typeof(OsVersion)) };
        if (RtlGetVersion(ref version) != 0 || version.build < 19041)
            throw new PlatformNotSupportedException("Portable hardware access needs Windows 10 2004 or newer.");
        ushort processMachine, nativeMachine;
        if (!IsWow64Process2(GetCurrentProcess(), out processMachine, out nativeMachine) || nativeMachine != 0x8664)
            throw new PlatformNotSupportedException("The bundled hardware driver supports AMD64 computers only.");
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ServiceStatus { public uint type, state, accepted, exit, specificExit, checkpoint, waitHint; }
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenSCManager(string machine, string database, uint access);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateService(IntPtr manager, string name, string displayName, uint access,
        uint type, uint start, uint error, string binary, string group, IntPtr tag, string dependencies,
        string account, string password);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool StartService(IntPtr service, uint count, IntPtr args);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool ControlService(IntPtr service, uint control, out ServiceStatus status);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool DeleteService(IntPtr service);
    [DllImport("advapi32.dll")]
    private static extern bool CloseServiceHandle(IntPtr service);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr security,
        uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    private static bool DriverAvailable()
    {
        IntPtr handle = CreateFile(@"\\?\GLOBALROOT\Device\PawnIO", 0xC0000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (handle == new IntPtr(-1)) return false;
        CloseHandle(handle);
        return true;
    }

    public PortableDriver(string source)
    {
        if (!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))
            throw new InvalidOperationException("Temporary hardware access needs UAC authorization.");
        // Serialize portable sessions, so one session cannot unload another session's driver.
        lease = new Mutex(false, @"Global\WebOBS.PortablePawnIO");
        try { locked = lease.WaitOne(0); }
        catch (AbandonedMutexException) { locked = true; }
        if (!locked) { lease.Dispose(); throw new IOException("Another WebOBS hardware session is active."); }
        try
        {
            if (DriverAvailable()) return; // Never stop or remove another application's installed driver.
            CheckPlatform();
            byte[] bytes = File.ReadAllBytes(source);
            using (var sha = SHA256.Create())
                if (BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant() != DriverHash)
                    throw new InvalidDataException("The official PawnIO driver checksum is invalid.");
            // The kernel loads a protected copy, preventing changes to a portable folder during UAC.
            directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "WebOBS-Driver-" + Guid.NewGuid().ToString("N"));
            if (Directory.Exists(directory)) throw new IOException("Temporary driver directory already exists.");
            var acl = new DirectorySecurity();
            var admins = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);
            acl.SetAccessRuleProtection(true, false);
            acl.SetOwner(admins);
            foreach (var sid in new[] { admins, new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
                acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None, AccessControlType.Allow));
            Directory.CreateDirectory(directory, acl);
            file = Path.Combine(directory, "PawnIO.sys");
            using (var output = new FileStream(file, FileMode.CreateNew, FileAccess.Write)) output.Write(bytes, 0, bytes.Length);
            manager = OpenSCManager(null, null, 3);
            if (manager == IntPtr.Zero) throw new Win32Exception();
            service = CreateService(manager, "WebOBS_PawnIO_" + Guid.NewGuid().ToString("N"),
                "WebOBS temporary hardware driver", 0x10034, 1, 3, 1, @"\??\" + file,
                null, IntPtr.Zero, null, null, null);
            if (service == IntPtr.Zero) throw new Win32Exception();
            if (!StartService(service, 0, IntPtr.Zero)) throw new Win32Exception();
            started = true;
            // Mark this demand-start record for deletion immediately; never enable auto-start.
            if (!DeleteService(service)) throw new Win32Exception();
            if (!DriverAvailable()) throw new IOException("The temporary PawnIO driver is unavailable.");
        }
        catch { try { Dispose(); } catch (IOException) { } throw; }
    }

    public void Dispose()
    {
        bool stopped = true;
        if (service != IntPtr.Zero)
        {
            ServiceStatus status;
            if (started && !ControlService(service, 1, out status) && Marshal.GetLastWin32Error() != 1062) stopped = false;
            DeleteService(service);
            CloseServiceHandle(service); service = IntPtr.Zero;
        }
        if (manager != IntPtr.Zero) { CloseServiceHandle(manager); manager = IntPtr.Zero; }
        if (stopped && file != null && File.Exists(file)) File.Delete(file); // One known temporary file only.
        if (stopped && directory != null && Directory.Exists(directory)) Directory.Delete(directory, false);
        if (locked) { lease.ReleaseMutex(); locked = false; }
        if (lease != null) { lease.Dispose(); lease = null; }
        if (!stopped) throw new IOException("The temporary driver could not be unloaded; no auto-start was installed.");
    }
}
