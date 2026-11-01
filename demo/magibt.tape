# MagiBT terminal UI on the demo data. Record from the repo root:
#   vhs demo/magibt.tape   ->  demo/magibt.gif

Output demo/magibt.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 470
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 70ms

Env MAGIBT_CONFIG "bills.example.toml"
Env MAGIBT_DATA "demo/data"

Hide
Type "export PS1='$ ' && python -m demo.seed >/dev/null && alias magibt=$PWD/tui/magibt.py && clear" Enter
Sleep 500ms
Show

Type "magibt" Sleep 400ms Enter
Sleep 2s

# building fees: the amount comes from a photo, so it is typed in by hand
Type "j" Sleep 600ms
Space Sleep 1.5s
Type "a" Sleep 800ms
Type "35,00" Sleep 500ms Enter
Sleep 1.5s
Type "h" Sleep 1s

# electricity is overdue: open its history and mark it paid
Type "j" Sleep 300ms Type "j" Sleep 300ms Type "j" Sleep 800ms
Space Sleep 1.5s
Type "p" Sleep 1.5s
Type "j" Sleep 400ms Type "j" Sleep 1s
Type "h" Sleep 1.2s

# payment details and links for a bill
Type "k" Sleep 300ms Type "k" Sleep 300ms Type "k" Sleep 600ms
Type "l" Sleep 3s
Escape Sleep 800ms

# subscriptions tab
Tab Sleep 2.5s
Tab Sleep 800ms
Type "q" Sleep 500ms

# the same data as plain tables
Type "magibt -s" Sleep 400ms Enter
Sleep 4s
