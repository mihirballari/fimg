# engine/send.sh
send_one() {
  local handle="$1"
  shift
  local message="$*"
  /usr/bin/osascript "$HOME/fimg/engine/send_imessage.applescript" "$handle" "$message"
}
