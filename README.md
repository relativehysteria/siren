Create a file -- `TOKEN` -- in the root directory of this bot and put your token
into it.

The logging level is based on the `SIREN_LOG_LEVEL` environment variable.
If it isn't set, it defaults to `info` (the levels are the same as the python
logging levels).

Requires py-cord and pynacl.

The codebase is not thoroughly tested and because I tried to write code without
explicit locks (only used events, queues, pipes), there may be some race
conditions present. So far, every now and then, a song doesn't get received
through the pipe and the player thread deadlocks. I don't know what causes this
but will try to find out. :|

### TODO
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

* On shuffle and clear, invalidate the song received from the caching process
  and get a new one (in `_song_player_target()`)

* Disconnect after a certain time of inactivity

* Write tests
