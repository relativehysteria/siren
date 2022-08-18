Create a file -- `TOKEN` -- in the root directory of this bot and put your token
into it.

Requires py-cord and pynacl.

The codebase is not thoroughly tested and because I tried to write code without
explicit locks (only used events, queues, pipes), there may be some race
conditions present. So far, every now and then, a song doesn't get received
through the pipe and the player thread deadlocks. I don't know what causes this
but will try to find out. :|

### TODO
* When the bot is kicked from a VC, the queue is not destroyed and the bot can't
  reconnect (because a queue for the guild is already present -- the bot thinks
  it is still connected to the voice chat).

* Optimize the command algorithm, especially the `/skip` command and any of the
  commands that toggle a state (e.g. `/shuffle` or `/pause`).
  Multiple `/skip` commands issued in rapid sequence _do_ in fact create a
  _noticeable_ delay, because the bot tries to lazily extract song metadata for
  _every one of those songs_ that have been skipped.  
  The first optimization is to make the command handler minimally-blocking.
  That is, respond to the commands with something like "Working on it...",
  then put them into a queue and evaluate the queue in the background.  
  Then perform some optimizations on the queue. I don't know what those
  optimizations are called, but e.g. if there are 3 `/shuffle` commands in a
  sequence, evaluate them as 1. Or if there are 4 `/pause` commands in a
  sequence, just remove them completely.

* Write a destructor for SongQueue and call it whenever the bot is disconnected
  from a voice chat.

* In SongQueue, set `_stop_threads`: unlock all blocking stuff and shit and
  close all pipes.

* On shuffle and clear, invalidate the song received from the caching process
  and get a new one (in `_song_player_target()`)

* If we're running on UNIX* and have root privs, decrease the process niceness
  in prioritized cache extractors

* Write tests
