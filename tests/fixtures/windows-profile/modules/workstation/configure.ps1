if ($args.Count -ne 2 -or $args[0] -cne 'two words' -or $args[1] -cne '$HOME; literal') { exit 11 }
if ($env:ETCH_TEST_VALUE -cne 'literal $HOME') { exit 12 }
[IO.File]::WriteAllText((Join-Path $pwd 'configured.txt'), 'ready')
