// Read-only LibreHardwareMonitor bridge. .NET Framework 4.7.2+, no PowerShell runtime.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using LibreHardwareMonitor.Hardware;

internal static class SensorBridge
{
    private static string libraryDirectory;
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 2097152 };
    private static PortableSession session;

    public static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        if (args.Length < 2)
        {
            Console.Error.WriteLine("Usage: WebOBSSensor.exe <library-directory> <config-path>");
            return 2;
        }
        libraryDirectory = Path.GetFullPath(args[0]);
        AppDomain.CurrentDomain.AssemblyResolve += ResolveLibrary;
        try
        {
            if (args.Length == 7 && args[2] == "--portable")
            {
                using (session = new PortableSession(int.Parse(args[3]), long.Parse(args[4]), args[5], long.Parse(args[6])))
                {
                    session.Connect();
                    try
                    {
                        using (var driver = new PortableDriver(Path.Combine(libraryDirectory, "..", "PawnIO", "PawnIO.sys")))
                            return Run(Path.GetFullPath(args[1]));
                    }
                    catch (Exception error)
                    {
                        if (!session.Stopped.WaitOne(0)) Emit(new { hardware = new object[0], error = error.Message });
                        return session.Stopped.WaitOne(0) ? 0 : 1;
                    }
                }
            }
            return Run(Path.GetFullPath(args[1]));
        }
        catch (Exception error)
        {
            Console.WriteLine(Json.Serialize(new { hardware = new object[0], error = error.Message }));
            return 1;
        }
    }

    private static void Emit(object packet)
    {
        string line = Json.Serialize(packet);
        if (session != null) session.Write(line);
        else { Console.WriteLine(line); Console.Out.Flush(); }
    }

    private static Assembly ResolveLibrary(object sender, ResolveEventArgs args)
    {
        string name = new AssemblyName(args.Name).Name;
        string path = Path.Combine(libraryDirectory, name + ".dll");
        return File.Exists(path) ? Assembly.LoadFrom(path) : null;
    }

    private static int Run(string configPath)
    {
        var computer = new Computer { IsCpuEnabled = true, IsGpuEnabled = true };
        int interval = 1000;
        DateTime lastConfigWrite = DateTime.MinValue;
        ApplyConfig(configPath, computer, ref interval, ref lastConfigWrite);
        computer.Open();
        try
        {
            while (session == null || !session.Stopped.WaitOne(0))
            {
                var timer = Stopwatch.StartNew();
                ApplyConfig(configPath, computer, ref interval, ref lastConfigWrite);
                var devices = new List<object>();
                var errors = new List<string>();
                foreach (IHardware hardware in computer.Hardware)
                {
                    try { ReadHardware(hardware, devices); }
                    catch (Exception error) { errors.Add(hardware.Name + ": " + error.Message); }
                }
                Emit(new { hardware = devices, error = errors.Count > 0 ? string.Join("; ", errors) : null,
                    access = session != null ? "portable-elevated" : "direct" });
                int wait = Math.Max(1, interval - (int)timer.ElapsedMilliseconds);
                if (session == null) Thread.Sleep(wait);
                else session.Stopped.WaitOne(wait);
            }
        }
        finally { computer.Close(); }
        return 0;
    }

    private static void ApplyConfig(string path, Computer computer, ref int interval, ref DateTime previousWrite)
    {
        try
        {
            if (!File.Exists(path)) return;
            DateTime updated = File.GetLastWriteTimeUtc(path);
            if (updated == previousWrite) return;
            var config = Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8));
            object value;
            if (config.TryGetValue("sensorIntervalMs", out value)) interval = Math.Max(1000, Math.Min(10000, Convert.ToInt32(value)));
            computer.IsMotherboardEnabled = config.TryGetValue("motherboardSensors", out value) && value is bool && (bool)value;
            computer.IsPowerMonitorEnabled = config.TryGetValue("powerMode", out value) && Convert.ToString(value) == "measured";
            previousWrite = updated;
        }
        catch (IOException) { } // Keep last valid configuration during atomic replacement.
        catch (Exception) { } // Invalid configuration does not stop hardware monitoring.
    }

    private static void ReadHardware(IHardware hardware, List<object> devices)
    {
        hardware.Update();
        bool validLowLevel = false;
        foreach (ISensor sensor in hardware.Sensors)
        {
            if ((sensor.SensorType == SensorType.Clock || sensor.SensorType == SensorType.Temperature) && sensor.Value.HasValue)
                validLowLevel = true;
        }
        var sensors = new List<object>();
        foreach (ISensor sensor in hardware.Sensors)
        {
            float? value = sensor.Value;
            if (value.HasValue && (float.IsNaN(value.Value) || float.IsInfinity(value.Value))) value = null;
            if (hardware.HardwareType == HardwareType.Cpu && !validLowLevel && sensor.SensorType == SensorType.Power && value == 0)
                value = null;
            Dictionary<string, float> voltageParameters = null;
            if (sensor.SensorType == SensorType.Voltage && sensor.Parameters.Count == 3 &&
                sensor.Parameters[0].Name.StartsWith("Ri [") && sensor.Parameters[1].Name.StartsWith("Rf [") &&
                sensor.Parameters[2].Name.StartsWith("Vf ["))
                voltageParameters = new Dictionary<string, float> {
                    { "ri", sensor.Parameters[0].Value }, { "rf", sensor.Parameters[1].Value }, { "vf", sensor.Parameters[2].Value }
                };
            sensors.Add(new { id = sensor.Identifier.ToString(), name = sensor.Name, type = sensor.SensorType.ToString(),
                value = value, voltageParameters = voltageParameters });
        }
        devices.Add(new { id = hardware.Identifier.ToString(), name = hardware.Name, type = hardware.HardwareType.ToString(),
            parentId = hardware.Parent != null ? hardware.Parent.Identifier.ToString() : null, sensors = sensors });
        foreach (IHardware child in hardware.SubHardware) ReadHardware(child, devices);
    }
}
