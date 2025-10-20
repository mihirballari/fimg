on run {targetPhone, targetMessage}
    tell application "Messages"
        set svc to first service whose service type is iMessage
        set buddyRef to buddy targetPhone of svc
        if targetMessage is not "" then
            send targetMessage to buddyRef
        end if
    end tell
end run
