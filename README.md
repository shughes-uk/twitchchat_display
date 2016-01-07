Twitch/Youtube Chat Display
===================

An app to display twitch and/or youtubechat primarily on a raspberry pi but does work on other systems
 
Usage
-----

Create `config.txt` like shown in `config_example.txt` and then run:

    python ./main.py

-d for debug messages , -t to subscribe to featured channels for testing

If you are using youtubechat you will have to supply the oauth_creds file  generated using the python-youtubechat project
You can try and grab depedencies using try_get_dependencies.py, getting pygame installed can be a fun time sometimes.


Dependencies
------------

 * python-twitch(https://github.com/ingwinlu/python-twitch)
 * [python-youtubechat](https://github.com/shughes-uk/python-youtubechat)
 * [python-twitchevents](https://github.com/shughes-uk/python-twitchevents)
 * [python-twitchchat](https://github.com/shughes-uk/python-twitchchat)
 * pygame
 * fonttools
 * webcolors
