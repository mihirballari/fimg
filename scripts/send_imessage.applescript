-- send_imessage.applescript
-- Usage: osascript send_imessage.applescript "<number or email>" "<message>"
on run argv
  if (count of argv) < 2 then return
  set target to item 1 of argv
  set textMsg to item 2 of argv
  tell application "Messages"
    activate
    set theService to first service whose service type is iMessage
    set theBuddy to buddy target of theService
    send textMsg to theBuddy
  end tell
end run

