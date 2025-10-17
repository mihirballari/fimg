# lib/resize.sh — simple WINCH hook
resize_on_redraw() {
  _cb="$1"
  trap "$_cb" WINCH
}
