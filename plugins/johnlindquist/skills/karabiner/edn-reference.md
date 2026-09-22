# EDN Syntax Reference

Comprehensive reference for Goku's EDN format.

## Complete Config Structure

```clojure
{
 ;; Global timing settings
 :default             true
 :alone               500    ;; to_if_alone timeout (ms)
 :delay               200    ;; sequence key delay (ms)
 :held                500    ;; held threshold (ms)
 :simlayer-threshold  140    ;; simultaneous detection (ms)

 ;; Custom modifier combinations
 :modifiers {:hyper [:command :shift :control :option]
             :meh   [:shift :control :option]
             :cos   [:command :option :shift]}

 ;; Input key aliases
 :froms {:delete {:key :delete_or_backspace}
         :return {:key :return_or_enter}
         :mouse1 {:pkey :button1}}

 ;; Output action aliases
 :tos {:spotlight {:key :spacebar :modi :command}
       :alfred    {:key :spacebar :modi :option}}

 ;; Shell command templates
 :templates {:open "open -a '%s'"
             :script "/path/to/script.sh %s"}

 ;; Application bundle IDs
 :applications {:chrome ["com.google.Chrome"]
                :code   ["com.microsoft.VSCode"]}

 ;; Device identifiers
 :devices {:hhkb [{:vendor_id 1278 :product_id 51966}]}

 ;; Input sources
 :input-sources {:us {:input_source_id "com.apple.keylayout.US"}}

 ;; Simlayer definitions
 :simlayers {:w-mode {:key :w}}

 ;; Standard layer definitions
 :layers {:caps-mode {:key :caps_lock :alone {:key :escape}}}

 ;; Main rules
 :main [{:des "Description" :rules []}]
}
```

## Keycode Categories

### Letters & Numbers
`:a` `:b` ... `:z`
`:1` `:2` ... `:0`

### Function Keys
`:f1` ... `:f24`

### Modifiers
`:left_command` `:right_command`
`:left_control` `:right_control`
`:left_option` `:right_option`
`:left_shift` `:right_shift`
`:caps_lock` `:fn`

### Navigation
`:up_arrow` `:down_arrow` `:left_arrow` `:right_arrow`
`:page_up` `:page_down` `:home` `:end`

### Editing
`:return_or_enter` `:escape` `:delete_or_backspace` `:delete_forward`
`:tab` `:spacebar`

### Punctuation
`:hyphen` `:equal_sign`
`:open_bracket` `:close_bracket`
`:backslash` `:non_us_backslash`
`:semicolon` `:quote`
`:grave_accent_and_tilde`
`:comma` `:period` `:slash`

### Special
`:vk_none` (no output)
`:f13` ... `:f24` (unused function keys for custom mappings)

## Modifier Prefix Table

| Prefix | Meaning | Full Name |
|--------|---------|-----------|
| `!` | Mandatory | Required to be held |
| `#` | Optional | May or may not be held |
| `C` | Left Command | `left_command` |
| `T` | Left Control | `left_control` |
| `O` | Left Option | `left_option` |
| `S` | Left Shift | `left_shift` |
| `Q` | Right Command | `right_command` |
| `W` | Right Control | `right_control` |
| `E` | Right Option | `right_option` |
| `R` | Right Shift | `right_shift` |
| `F` | Fn | `fn` |
| `P` | Caps Lock | `caps_lock` |
| `!!` | Hyper | Cmd+Ctrl+Opt+Shift |
| `##` | Any | Any modifier(s) |

### Examples

```clojure
:!Ca           ;; Cmd+A (mandatory)
:!CTSa         ;; Cmd+Ctrl+Shift+A
:!!a           ;; Hyper+A
:##escape      ;; Escape with any modifiers
:#Ca           ;; A with optional Cmd
```

## Rule Formats

### Basic Mapping
```clojure
[:from :to]
[:a :b]                    ;; a -> b
[:!Ca :!Cb]                ;; Cmd+A -> Cmd+B
```

### With Condition
```clojure
[:from :to :condition]
[:a :b :chrome]            ;; a -> b only in Chrome
[:a :b [:chrome :!safari]] ;; in Chrome, not Safari
```

### With Options
```clojure
[:from :to nil {:alone :key}]
[:from :to :cond {:alone :key :held :other}]
```

### Multiple Outputs
```clojure
[:a [:b :c :d]]            ;; a -> b, c, d sequence
[:a [{:key :b} {:key :c}]] ;; explicit key maps
```

### Simultaneous Input
```clojure
[[:j :k] :escape]          ;; j+k together -> escape
[[:a :s :d] :f13]          ;; a+s+d together -> f13
```

## Option Keys

```clojure
{
 :alone :key               ;; to_if_alone
 :held :key                ;; to_if_held_down
 :afterup :key             ;; to_after_key_up
 :delayed {:invoked :x     ;; to_delayed_action
           :canceled :y}
 :params {:basic.to_if_alone_timeout_milliseconds 200
          :basic.to_if_held_down_threshold_milliseconds 200}
}
```

## Variable Operations

### Set Variable
```clojure
[:w ["mode" 1]]            ;; w sets mode=1
[:w [:w ["mode" 1]]]       ;; w outputs w AND sets mode=1
```

### Use Variable as Condition
```clojure
[:a :b ["mode" 1]]         ;; a -> b when mode=1
[:a :b ["mode" 0]]         ;; a -> b when mode=0
```

### Toggle Pattern
```clojure
[:w ["mode" 1] nil {:afterup ["mode" 0] :alone :w}]
;; Hold w: mode=1, Release: mode=0, Tap: outputs w
```

## Layer Patterns

### Simlayer (Simultaneous)
```clojure
{:simlayers {:nav {:key :spacebar}}
 :main [{:rules [:nav
                 [:h :left_arrow]
                 [:j :down_arrow]]}]}
```

### Simlayer with Modifier Requirement
```clojure
{:simlayers {:nav {:key :spacebar
                   :modi {:mandatory [:left_control]}}}}
```

### Standard Layer (Tap/Hold)
```clojure
{:layers {:caps {:key :caps_lock
                 :alone {:key :escape}}}}
```

### Layer with Afterup Reset
```clojure
{:layers {:esc {:key :escape
                :alone [{:key :escape}
                        {:set ["mode1" 0]}
                        {:set ["mode2" 0]}]}}}
```

## Template Syntax

Templates use Java format specifiers:

```clojure
{:templates {:single "command %s"           ;; One argument
             :multi  "cmd %s %s"            ;; Two arguments
             :typed  "cmd %d items"}}       ;; Integer

;; Usage
[:a [:single "arg1"]]
[:b [:multi "arg1" "arg2"]]
```

## Mouse/Pointing Device

### Mouse Buttons
```clojure
{:pkey :button1}           ;; Left click
{:pkey :button2}           ;; Right click
{:pkey :button3}           ;; Middle click
{:pkey :button4}           ;; Back
{:pkey :button5}           ;; Forward
```

### Mouse Key Actions
```clojure
{:mkey {:x 100}}           ;; Move mouse X
{:mkey {:y 100}}           ;; Move mouse Y
{:mkey {:vwheel -32}}      ;; Scroll vertical
{:mkey {:hwheel 32}}       ;; Scroll horizontal
{:mkey {:speed 0.5}}       ;; Speed multiplier
```

## Shell Command Patterns

### Direct Command
```clojure
[:!!1 "open -a Safari"]
```

### With Template
```clojure
{:templates {:app "open -a '%s'"}}
[:!!1 [:app "Safari"]]
```

### AppleScript
```clojure
[:!!1 "osascript -e 'tell app \"Finder\" to activate'"]
```

### Complex AppleScript
```clojure
{:templates {:paste "osascript -e '
  set the clipboard to \"%s\"
  tell application \"System Events\"
    keystroke \"v\" using command down
  end tell'"}}
```

## Application Bundle IDs

Find bundle IDs:
```bash
osascript -e 'id of app "App Name"'
mdls -name kMDItemCFBundleIdentifier /Applications/App.app
```

Common IDs:
```clojure
{:applications {
  :chrome   ["com.google.Chrome"]
  :safari   ["com.apple.Safari"]
  :firefox  ["org.mozilla.firefox"]
  :vscode   ["com.microsoft.VSCode"]
  :cursor   ["com.todesktop.230313mzl4w4u92"]
  :terminal ["com.apple.Terminal"]
  :iterm    ["com.googlecode.iterm2"]
  :wezterm  ["com.github.wez.wezterm"]
  :finder   ["com.apple.finder"]
  :slack    ["com.tinyspeck.slackmacgap"]
}}
```

## Device Identification

Find device IDs:
1. Open Karabiner-Elements Preferences
2. Go to Devices tab
3. Note Vendor ID and Product ID

```clojure
{:devices {:my-keyboard [{:vendor_id 1234
                          :product_id 5678}]}}
```

## Profile Configuration

```clojure
{:profiles {
  :Default {:default true
            :sim 250          ;; Simultaneous window
            :delay 500        ;; Delayed action delay
            :alone 1000       ;; to_if_alone timeout
            :held 500}        ;; to_if_held_down threshold
  :Gaming {:default false
           :sim 100}}}
```
