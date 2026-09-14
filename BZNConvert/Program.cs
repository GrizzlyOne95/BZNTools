using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text;
using BZNParser.Tokenizer;
using BZNParser.Battlezone;

namespace BZNConvert
{
    class Program
    {
        static int Main(string[] args)
        {
            // Minimal, safe CLI: BZNConvert.exe <path> [--ascii] [--recursive] [--output <path>] [--verify] [--force]
            if (args.Length == 0)
            {
                Console.Error.WriteLine("Usage: BZNConvert <path> [--ascii] [--recursive] [--output <dir|file>] [--verify] [--force]");
                return 2;
            }

            string inputPath = args[0];
            bool ascii = args.Contains("--ascii");
            bool recursive = args.Contains("--recursive");
            string? outputPath = null;
            int outIndex = Array.IndexOf(args, "--output");
            if (outIndex >= 0 && outIndex + 1 < args.Length)
                outputPath = args[outIndex + 1];
            bool verify = args.Contains("--verify");
            bool force = args.Contains("--force");

            // Discover whether path is directory or file
            var paths = new List<string>();
            if (Directory.Exists(inputPath))
            {
                // enumerate files
                foreach (var file in Directory.GetFiles(inputPath, "*.bzn", SearchOption.TopDirectoryOnly))
                    paths.Add(file);
                if (recursive)
                {
                    foreach (var file in Directory.GetFiles(inputPath, "*.bzn", SearchOption.AllDirectories))
                        paths.Add(file);
                }
            }
            else if (File.Exists(inputPath))
            {
                paths.Add(inputPath);
            }
            else
            {
                Console.Error.WriteLine("Input not found");
                return 3;
            }

            if (ascii)
            {
                Console.WriteLine("Input is ASCII BZN; skipping rewrite by default");
            }

            int safeCount = 0;
            foreach (var p in paths)
            {
                try
                {
                    // Phase 3: load binary, convert to ASCII, re-read and verify if requested
                    using var fs = File.OpenRead(p);
                    var reader = new BZNStreamReader(fs, p);
                    var hints = BattlezoneBZNHints.BuildHintsBZ1() ?? BattlezoneBZNHints.BuildHintsBZ2();
                    var bzn = new BZNFileBattlezone(reader, hints);
                    var memOut = new MemoryStream();
                    using (var writer = new BZNStreamWriter(memOut, reader.Format, reader.Version))
                    {
                        bzn.Write(writer, binary:false, save:false);
                    }
                    // Disposing the writer closes memOut, so re-reading it directly
                    // always threw "Cannot access a closed Stream" and the verify
                    // path could never succeed. ToArray() is still valid on a
                    // closed MemoryStream, so round-trip through the bytes.
                    var asciiBytes = memOut.ToArray();
                    using var verifyStream = new MemoryStream(asciiBytes);
                    var verifyReader = new BZNStreamReader(verifyStream, p + ":ascii");
                    var vHints = BattlezoneBZNHints.BuildHintsBZ1() ?? BattlezoneBZNHints.BuildHintsBZ2();
                    var vBzn = new BZNFileBattlezone(verifyReader, vHints);
                    safeCount++;

                    var mal = bzn.Malformations.GetMalformations((BZNParser.Tokenizer.Malformation?)null);
                    if (mal.Length > 0)
                    {
                        Console.WriteLine($"{Path.GetFileName(p)}: {mal.Length} malformation(s)");
                        foreach (var m in mal.Take(12))
                            Console.WriteLine($"    {m.Type} {string.Join(", ", m.Fields ?? Array.Empty<object>())}");
                    }
                    else
                    {
                        Console.WriteLine($"{Path.GetFileName(p)}: clean");
                    }
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"Failed: {p} -> {ex.Message}");
                    if (!force) return 4;
                }
            }

            Console.WriteLine($"Converted: {safeCount} / {paths.Count}");
            return 0;
        }
    }
}
