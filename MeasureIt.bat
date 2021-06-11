call conda.bat activate qcodes
%USERPROFILE%\Anaconda3\envs\qcodes\python.exe %USERPROFILE%\MeasureIt\GUI\GUI_Measureit.py
timeout /t -1
call conda deactivate
