on run argv
	set phone to item 1 of argv
	set msg to item 2 of argv
	tell application "Messages"
		set s to 1st service whose service type = iMessage
		set theBuddy to buddy phone of s
		send msg to theBuddy
	end tell
end run
