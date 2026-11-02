@echo off
set "PYTHONPATH=%~dp0.pylibs"
set "PYTHONIOENCODING=utf-8"
set "MPLCONFIGDIR=%~dp0.cache\mpl"
"C:\Users\Asus\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" %*
