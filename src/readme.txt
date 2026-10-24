HI thank you for open this read me file, This is a read me file to tell you how to run my project
the back up of all file i implemented  is on the baks folder  A direct tree of magnetic ui folder on the appendix part of project report 
when crash, you can recover the the folder by installing the new magnetic ui and put all the baks file to the direct tree location the report appendix shown.

setup steps:

requirements:     your docker need running ,  anaconda,  nvidia gpu 16gb vram is required  or the system will be slow


1. create a new environment. (optional):

       conda create -n mgui python=3.12 -y
       conda activate mgui

2. install magentic-ui:

       pip install "magentic-ui[ollama]==0.1.6"

3. install the browser playwright :

       playwright install chromium

4. replace the installed magentic-ui whole folder with src/magentic_ui in this repository. You can find the installed magentic-ui by:

       pip show magentic-ui

5. put your openai api key in magentic_ui/hl_config.py, in the OPENAI_API_KEY field. 


6. start the server:

       docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 --name ollama -e OLLAMA_FLASH_ATTENTION=1 -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_CONTEXT_LENGTH=32768 ollama/ollama

7. pull the model :

       docker exec ollama ollama pull qwen3:14b

8. build the no-thinking model.
   first, in powerShell, first find the foldow this readme file in
   then find the file  —  qwen3-nothink.Modelfile:

       dir qwen3-nothink.Modelfile

   then run:

       docker cp qwen3-nothink.Modelfile ollama:/tmp/m
       docker exec ollama ollama create qwen3-nothink -f /tmp/m

install success

9.   run the magenticui in powershell:    

		magentic-ui --port 8081

 10. open the magnetic ui gui page 
choose setting ---- advanced setting ---------
                              change the model field to  ：qwen3-nothink   
                              change the visionfield to     : false


 fininally:     model: qwen3-nothink              <--------- thisvalue
    		 host: http://localhost:11434
      		 max_retries: 5
      		 model_info:
        	 vision: false             <------------------------  this value
       		 function_calling: true
       		 json_output: true
        	 family: unknown
       		 structured_output: false
        	 multiple_system_messages: false
 
fininally:   click  Apply changes  and open a new window,  then, you can run it on qwen 3 no think 


11. run a task ten time still in the current folder: you need to see this file :  eval_config.yaml

then run:

 
       $env:PYTHONIOENCODING="utf-8"

       $task = "Please use Google Maps to check How long does it take to walk from King's College London's Strand Campus to Big Ben? (Answer Precise to minute)."

       1..10 | ForEach-Object { magentic-cli --work-dir ".\work_$_" --config eval_config.yaml --autonomous --action-policy never --old-cli --task $task *> "run_$_.log"; docker ps -q --filter ancestor=ghcr.io/microsoft/magentic-ui-browser:0.0.2 | ForEach-Object { docker rm -f $_ } }




   logs go from run_1.log   to  run_10.log in this folder.

you can change task  by replace the string behind  $task  eg : $task = "the another task"

