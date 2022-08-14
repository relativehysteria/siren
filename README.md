Create a file -- `TOKEN` -- in the root directory of this bot and put your token
into it.

Requires py-cord and pynacl.

### TODO
* When the bot is kicked from a VC, the queue is not destroyed and the bot can't
  reconnect (because a queue for the guild is already present -- the bot thinks
  it is still connected to the voice chat).

* Write a background thread that will extract and cache the song
  metadata while the bot is playing one already. At the moment the metadata is
  lazily extracted _one song before_ it starts playing. This is good, because
  a single `/skip` command won't create a small delay before the song starts
  playing (we don't have to wait for the metadata to be extracted as it is
  already cached). However it's not sufficient for multiple successive `/skip`s.  
  It could also take care of re-caching the next song whenever `/shuffle` gets
  called.

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

* Create an embed if we play a single song and not a playlist.

* Create a `/current` command to show an embed for the currently playing song.
