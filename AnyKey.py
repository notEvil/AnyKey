# encoding=utf-8
'''
At the beginning, AnyKey was a function for AutoHotKey (Windows) which was called on every key stroke (hence the name) and allowed for hierarchical abbreviations.
Then it was rewritten for AutoKey (py3; Linux). Unfortunately AutoKey was very annoying.
The need for a less annoying solution led to this python 3 application (Linux).

AnyKey is suspended on startup.
Use toggle suspend modifier+key combination to unsuspend.

Overview:
- grabs some input device using evdev (exclusive access)
- transforms the sequence of events into a sequence of characters
- looks for matching abbreviations
- sends appropriate events to device 'uinput'
  - does NOT perform any key-to-key mapping !!
  - except for undo ops

Features:
- operates between dev and X
  -> needs root, low level
- undo performed abbreviations with any modifier+key combination (UNDO)
  -> if annoying: create an abbreviation with higher priority
- undo performed abbreviations with a single modifier
  - key down key up within timeout: single undo
  - key down and hold within timeout to key up: successive undos
- clear memory with any modifier+key combination (CLEAR)
  -> usually on context change, for instance on Page Up
- toggle suspend with any modifier+key combination

Details:
- calls "xset -q" to retrieve and use auto repeat delay and rate.

Syntax:
python3 /path/to/AnyKey.py -dev /path/to/dev

User Settings:
see section below
'''

import sys
args = sys.argv
import evdev
codes = evdev.ecodes
import collections
import subprocess as sub
import re
import time

## Modifier class
mods = ['LShift', 'RShift', 'LCtrl', 'RCtrl', 'LMeta', 'LAlt', 'RAlt']
ModC = collections.namedtuple('ModC', mods)
NoMod = ModC(**{m: 0 for m in mods})

## special characters
UNDO = '\b'
CLEAR = '\0'
TOGGLE = '\1' # internally, don't use this in Characters


##
# User Settings
##

Dev = args[args.index('-dev') + 1]

MaxHist = 32 # max number of undo steps

Abbrs = (
    # abbreviations at same depth have equal priority
    # abbreviations at lower depth have higher priority
    [('aue', 'aue'), # Mauer, bauen
     ('Aue', 'Aue'), # Auerhahn, Auenland
     ('eue', 'eue'), # Feuer, neuen
     ('Euer', 'Euer'),
     ('Baguette', 'Baguette'),
     ('que', 'que'), # quer, bequem
     ('Quer', 'Quer'),
     ('tuell', 'tuell'), # aktuell, virtuell
     ('xuell', 'xuell'), # sexuell, Sexuell
     ('zuerst', 'zuerst'),
     ('Zuerst', 'Zuerst'),
     ('koeff', 'koeff'),
     ('Koeff', 'Koeff'),
     ('oexist', 'oexist'), # Koexistenz, koexistieren
    ],
    [('ae', 'ä'),('oe', 'ö'), ('ue', 'ü'),
     ('AE', 'Ä'), ('OE', 'Ö'), ('UE', 'Ü'),
     ('EUR', '€'), ('SS', 'ß'),
    ],
)


Modifiers = {'KEY_LEFTSHIFT': 'LShift',
             'KEY_RIGHTSHIFT': 'RShift',
             'KEY_CAPSLOCK': 'LCtrl',
             'KEY_RIGHTCTRL': 'RCtrl',
             'KEY_LEFTMETA': 'LMeta',
             'KEY_LEFTALT': 'LAlt',
             'KEY_RIGHTALT': 'RAlt'}
CapslockKey = 'KEY_ESC'

ToggleMod = NoMod._replace(RAlt=1)
ToggleKey = 'KEY_F12'
UndoModKeys = ['KEY_CAPSLOCK']
UndoModTimeout = 0.25 # seconds


Characters = {
    NoMod: {
        ## 1st row
        #'KEY_ESC': '',
        #'KEY_F1': '',
        #'KEY_F2': '',
        #'KEY_F3': '',
        #'KEY_F4': '',
        #'KEY_F5': '',
        #'KEY_F6': '',
        #'KEY_F7': '',
        #'KEY_F8': '',
        #'KEY_F9': '',
        #'KEY_F10': '',
        #'KEY_F11': '',
        #'KEY_F12': '',
        #'KEY_SYSRQ': '', # Druck
        #'KEY_SCROLLLOCK': '', # Rollen
        #'KEY_PAUSE': '', # Pause
        ## 2nd row
        'KEY_GRAVE': '`',
        'KEY_1': '1',
        'KEY_2': '2',
        'KEY_3': '3',
        'KEY_4': '4',
        'KEY_5': '5',
        'KEY_6': '6',
        'KEY_7': '7',
        'KEY_8': '8',
        'KEY_9': '9',
        'KEY_0': '0',
        'KEY_MINUS': '-',
        'KEY_EQUAL': '=',
        'KEY_BACKSPACE': UNDO,
        #'KEY_INSERT': '',
        'KEY_HOME': CLEAR,
        'KEY_PAGEUP': CLEAR,
        #'KEY_NUMLOCK': '',
        'KEY_KPSLASH': '/',
        'KEY_KPASTERISK': '*',
        'KEY_KPMINUS': '-',
        ## 3rd row
        #'KEY_TAB': '',
        'KEY_Q': 'q',
        'KEY_W': 'w',
        'KEY_E': 'f',
        'KEY_R': 'p',
        'KEY_T': 'g',
        'KEY_Y': 'j',
        'KEY_U': 'l',
        'KEY_I': 'u',
        'KEY_O': 'y',
        'KEY_P': ';',
        'KEY_LEFTBRACE': '[',
        'KEY_RIGHTBRACE': ']',
        'KEY_ENTER': '\n',
        'KEY_DELETE': CLEAR,
        'KEY_END': CLEAR,
        'KEY_PAGEDOWN': CLEAR,
        'KEY_KP7': '7',
        'KEY_KP8': '8',
        'KEY_KP9': '9',
        'KEY_KPPLUS': '+',
        ## 4th row
        #'KEY_CAPSLOCK': '',
        'KEY_A': 'a',
        'KEY_S': 'r',
        'KEY_D': 's',
        'KEY_F': 't',
        'KEY_G': 'd',
        'KEY_H': 'h',
        'KEY_J': 'n',
        'KEY_K': 'e',
        'KEY_L': 'i',
        'KEY_SEMICOLON': 'o',
        'KEY_APOSTROPHE': '\'',
        'KEY_BACKSLASH': '\n',
        'KEY_KP4': '4',
        'KEY_KP5': '5',
        'KEY_KP6': '6',
        ## 5th row
        #'KEY_LEFTSHIFT': '',
        'KEY_102ND': '\\',
        'KEY_Z': 'z',
        'KEY_X': 'x',
        'KEY_C': 'c',
        'KEY_V': 'v',
        'KEY_B': 'b',
        'KEY_N': 'k',
        'KEY_M': 'm',
        'KEY_COMMA': ',',
        'KEY_DOT': '.',
        'KEY_SLASH': '/',
        #'KEY_RIGHTSHIFT': '',
        'KEY_UP': CLEAR,
        'KEY_KP1': '1',
        'KEY_KP2': '2',
        'KEY_KP3': '3',
        'KEY_KPENTER': '\n',
        ## 6th row
        #'KEY_LEFTCTRL': '',
        #'KEY_LEFTMETA': '',
        #'KEY_LEFTALT': '',
        'KEY_SPACE': ' ',
        #'KEY_RIGHTALT': '',
        #'KEY_COMPOSE': '', # Menu
        #'KEY_RIGHTCTRL': '',
        'KEY_LEFT': CLEAR,
        'KEY_DOWN': CLEAR,
        'KEY_RIGHT': CLEAR,
        'KEY_KP0': '0',
        'KEY_KPDOT': '.',
    },

    NoMod._replace(RAlt=1): {
        'KEY_A': 'ä',
        'KEY_SEMICOLON': 'ö',
        'KEY_I': 'ü',
        'KEY_D': 'ß',
        'KEY_5': '€',
    },
}

shiftChars = {
    ## 1st row
    #'KEY_ESC': '',
    #'KEY_F1': '',
    #'KEY_F2': '',
    #'KEY_F3': '',
    #'KEY_F4': '',
    #'KEY_F5': '',
    #'KEY_F6': '',
    #'KEY_F7': '',
    #'KEY_F8': '',
    #'KEY_F9': '',
    #'KEY_F10': '',
    #'KEY_F11': '',
    #'KEY_F12': '',
    #'KEY_SYSRQ': '', # Druck
    #'KEY_SCROLLLOCK': '', # Rollen
    #'KEY_PAUSE': '', # Pause
    ## 2nd row
    'KEY_GRAVE': '~',
    'KEY_1': '!',
    'KEY_2': '@',
    'KEY_3': '#',
    'KEY_4': '$',
    'KEY_5': '%',
    'KEY_6': '^',
    'KEY_7': '&',
    'KEY_8': '*',
    'KEY_9': '(',
    'KEY_0': ')',
    'KEY_MINUS': '_',
    'KEY_EQUAL': '+',
    #'KEY_BACKSPACE': '',
    #'KEY_INSERT': '',
    'KEY_HOME': CLEAR,
    'KEY_PAGEUP': CLEAR,
    #'KEY_NUMLOCK': '',
    #'KEY_KPSLASH': '/',
    #'KEY_KPASTERISK': '*',
    #'KEY_KPMINUS': '-',
    ## 3rd row
    #'KEY_TAB': '',
    'KEY_Q': 'Q',
    'KEY_W': 'W',
    'KEY_E': 'F',
    'KEY_R': 'P',
    'KEY_T': 'G',
    'KEY_Y': 'J',
    'KEY_U': 'L',
    'KEY_I': 'U',
    'KEY_O': 'Y',
    'KEY_P': ':',
    'KEY_LEFTBRACE': '{',
    'KEY_RIGHTBRACE': '}',
    #'KEY_ENTER': '\n',
    'KEY_DELETE': CLEAR,
    'KEY_END': CLEAR,
    'KEY_PAGEDOWN': CLEAR,
    #'KEY_KP7': '7',
    #'KEY_KP8': '8',
    #'KEY_KP9': '9',
    #'KEY_KPPLUS': '+',
    ## 4th row
    #'KEY_CAPSLOCK': '',
    'KEY_A': 'A',
    'KEY_S': 'R',
    'KEY_D': 'S',
    'KEY_F': 'T',
    'KEY_G': 'D',
    'KEY_H': 'H',
    'KEY_J': 'N',
    'KEY_K': 'E',
    'KEY_L': 'I',
    'KEY_SEMICOLON': 'O',
    'KEY_APOSTROPHE': '"',
    'KEY_BACKSLASH': '\n',
    #'KEY_KP4': '4',
    #'KEY_KP5': '5',
    #'KEY_KP6': '6',
    ## 5th row
    #'KEY_LEFTSHIFT': '',
    'KEY_102ND': '|',
    'KEY_Z': 'Z',
    'KEY_X': 'X',
    'KEY_C': 'C',
    'KEY_V': 'V',
    'KEY_B': 'B',
    'KEY_N': 'K',
    'KEY_M': 'M',
    'KEY_COMMA': '<',
    'KEY_DOT': '>',
    'KEY_SLASH': '?',
    #'KEY_RIGHTSHIFT': '',
    'KEY_UP': CLEAR,
    #'KEY_KP1': '1',
    #'KEY_KP2': '2',
    #'KEY_KP3': '3',
    #'KEY_KPENTER': '\n',
    ## 6th row
    #'KEY_LEFTCTRL': '',
    #'KEY_LEFTMETA': '',
    #'KEY_LEFTALT': '',
    #'KEY_SPACE': ' ',
    #'KEY_RIGHTALT': '',
    #'KEY_COMPOSE': '', # Menu
    #'KEY_RIGHTCTRL': '',
    'KEY_LEFT': CLEAR,
    'KEY_DOWN': CLEAR,
    'KEY_RIGHT': CLEAR,
    #'KEY_KP0': '0',
    #'KEY_KPDOT': '.',
}

shiftRAltChars = {
    'KEY_A': 'Ä',
    'KEY_SEMICOLON': 'Ö',
    'KEY_I': 'Ü',
}

## add shift characters
for l in 0, 1:
    lmod = NoMod._replace(LShift=l)
    for r in 0, 1:
        if not (l or r):
            continue
        rmod = lmod._replace(RShift=r)

        Characters[rmod] = shiftChars
        Characters[rmod._replace(RAlt=1)] = shiftRAltChars

##
# End of User Settings
##


Modifiers = {codes.ecodes[key]: value for key, value in Modifiers.items()}
CapslockKey = codes.ecodes[CapslockKey]

ToggleKey = codes.ecodes[ToggleKey]
UndoModKeys = [codes.ecodes[k] for k in UndoModKeys]

Characters = {mod: {codes.ecodes[key]: value
                    for key, value in x.items()}
              for mod, x in Characters.items()}

Characters.setdefault(ToggleMod, {})[ToggleKey] = TOGGLE

## derived
ModifierKeys = {value: key for key, value in Modifiers.items()}

ToggleKeys = [ModifierKeys[ToggleMod._fields[i]] for i, v in enumerate(ToggleMod) if v]
ToggleKeys.append(ToggleKey)
UndoMods = [NoMod._replace(**{Modifiers[k]: 1}) for k in UndoModKeys]

SendCodes = {value: (mod, key)
             for mod, x in sorted(Characters.items(), reverse=True)
             for key, value in x.items() }


## globals
KeyCode = codes.EV_KEY

Hist = collections.deque()
Matches = []

## devs
dev = evdev.InputDevice(Dev)
Ui = evdev.UInput()#events=dev.capabilities())

## print events
#_write = Ui.write
#_write_event = Ui.write_event
#class Ui(object):
    #i = 1
    #def write(self, t, c, v):
        #print('{} event at {:.6f}, code {:02}, type {:02}, val {:02}'.format(Ui.i, time.time(), c, t, v))
        #Ui.i += 1
        #return _write(t, c, v)
    #def write_event(self, x):
        #if x.type == KeyCode:
            #print(Ui.i, x)
            #Ui.i += 1
        #return _write_event(x)
#Ui = Ui()


## main functions
send_ = Ui.write_event

def sendMod(mod):
    '''
    sends necessary key up/down events
    '''
    for i, (V, v) in enumerate(zip(Mod, mod)):
        if V == v:
            continue
        #print(mod._fields[i], v)
        Ui.write(KeyCode, ModifierKeys[mod._fields[i]], v)

def send(s):
    '''
    produces events from a string
    '''
    #print(repr(s))
    if len(s) == 0:
        return

    # temp up keys
    for k in Down:
        Ui.write(KeyCode, k, 0)
    TempUp.extend(Down)
    del Down[::]

    if CapslockOn:
        #print('Capslock off')
        Ui.write(KeyCode, CapslockKey, 1)
        Ui.write(KeyCode, CapslockKey, 0)

    global Mod
    original = Mod

    for c in s:
        mod, k = SendCodes[c]

        sendMod(mod)
        Mod = mod

        #print(repr(c), k)
        Ui.write(KeyCode, k, 1)
        Ui.write(KeyCode, k, 0)

    sendMod(original)
    Mod = original

    if CapslockOn:
        #print('Capslock on')
        Ui.write(KeyCode, CapslockKey, 1)
        Ui.write(KeyCode, CapslockKey, 0)
    #print('-')


def getBD(a):
    '''
    finds b and the corresponding depth in Abbrs
    '''
    for d, abbrs in enumerate(Abbrs):
        for aa, b in abbrs:
            if aa == a:
                return b, d
    return None, None


def reproduce(n, revHist=None):
    '''
    uses revHist to reproduce the last n characters that are visible
    '''
    if revHist is None:
        revHist = reversed(Hist)

    clear = 0
    r = []
    for t, hClear, hWrite in revHist:
        l = len(hWrite)
        if clear == 0:
            if n <= l:
                r.append(hWrite[-n::])
                n = 0
                break

            r.append(hWrite)
            n -= l

        else: # clear != 0
            if clear < l:
                l -= clear
                if n <= l:
                    r.append(hWrite[(l - n):l:])
                    n = 0
                    break

                r.append(hWrite[:l:])
                n -= l
                clear = 0
            else:
                clear -= l

        clear += hClear

    return ''.join(reversed(r))


def undo(n, chars=False):
    '''
    undoes the last n steps or characters by sending an appropriate sequence of key strokes.
    globals are not modified in any way
    '''
    #if len(Hist) < n:
        #n = len(Hist)
    if n == 0:
        return 0, ''

    revHist = reversed(Hist)
    minC = 0
    c = 0
    i = 0
    for t, hClear, hWrite in revHist:
        c -= len(hWrite)
        if c < minC:
            minC = c

        c += hClear

        if len(hWrite) == 0 or (chars and hClear != 0): # skip no-writes, and abbrs if in char mode
            continue

        i += 1
        if i == n:
            break

    clear = -minC

    if minC != c:
        write = reproduce(c - minC, revHist=revHist)
    else:
        write = ''

    send((UNDO*clear) + write)

    return clear, write


def addToHist(matches, clear, write):
    '''
    and enforces history limit on the fly
    '''
    if len(Hist) == MaxHist:
        Hist.popleft()
    Hist.append((matches, clear, write))


repeat = dev.repeat

## get X auto repeat settings
proc = sub.Popen(['xset', '-q'], stdout=sub.PIPE)
out = proc.stdout.read().decode()
match = next(re.finditer(r'^\s*auto repeat delay:\s*(?P<delay>\d+)\s*repeat rate:\s*(?P<rate>\d+)', out, re.MULTILINE))
delay = int(match.group('delay')) # = delay
rate = int(match.group('rate')) # = rate, higher = slower

nRepeat = evdev.device.KbdInfo(delay=rate, repeat=delay) # interchanged


def _undo(): # used to be global
    undo(1)

    if len(Hist) != 0:
        global Matches
        Matches, t, t = Hist.pop()
    else:
        #print 'UNDO'
        send(UNDO)

suspended = True

try:
    resuming = False
    suspending = False
    Mod = NoMod
    CapslockOn = False
    Down = []
    TempUp = []
    undoModT = 0
    undoModHold = False

    for event in dev.read_loop():
        if suspended: # minimal overhead during suspend
            if event.type != KeyCode: # non key event
                continue

            key = event.code
            if key not in ToggleKeys:
                continue

            if event.value == 0: # on up
                try: Down.remove(key)
                except ValueError: pass

                if len(Down) != 0:
                    continue

                if resuming:
                    suspended = False

                    Hist.clear()
                    Matches = []

                    resuming = False
                    Mod = NoMod
                    CapslockOn = False # might lead to issues if Capslock is on during toggle
                    del Down[::]
                    del TempUp[::]
                    undoModT = 0
                    undoModHold = False

                    dev.grab()
                    dev.repeat = nRepeat

                elif suspending:
                    suspending = False

                    dev.repeat = repeat
                    dev.ungrab()

            elif event.value == 1: # on down
                Down.append(key)

                if len(Down) == len(ToggleKeys):
                    resuming = True

            continue


        if event.type != KeyCode: # non key event
            send_(event)
            continue

        key = event.code

        #if key == codes.KEY_TAB: # debug exit
            #break

        if event.value == 0: # on up
            mod = Modifiers.get(key, None)
            if mod is None:
                try:
                    Down.remove(key)
                except ValueError: # key up already happened
                    try: TempUp.remove(key)
                    except ValueError: pass
                    continue
            else:
                Mod = Mod._replace(**{mod: 0})

                undoModHold = False
                if undoModT != 0 and (time.time() - undoModT) <= UndoModTimeout: # undo mod up
                    undoModT = time.time() # prepare undo mod hold
                    send_(event)
                    _undo()
                    continue

            send_(event)
            continue

        elif event.value == 1: # on down
            mod = Modifiers.get(key, None)
            if mod is None:
                Down.append(key)
            else:
                Mod = Mod._replace(**{mod: 1})

                if Mod in UndoMods:
                    if undoModT != 0 and (time.time() - undoModT) <= UndoModTimeout:
                        undoModHold = True # start undo mod hold
                    undoModT = time.time() # prepare undo mod

                send_(event)
                continue

            undoModT = 0

            if key == CapslockKey:
                CapslockOn = not CapslockOn
                send_(event)
                continue

        else: # on hold
            if key in TempUp:
                TempUp.remove(key)
                Down.append(key)
                event.value = 1

            elif undoModHold: # no test for UndoMod key here ;)
                _undo()
                continue

        if CapslockOn:
            shift = 0 if Mod.LShift or Mod.RShift else 1
            mod = Mod._replace(LShift=shift, RShift=shift)
        else:
            mod = Mod
        char = Characters.get(mod, {}).get(key, None)

        if char is None: # not matching
            send_(event)
            continue

        if char == TOGGLE:
            suspended = True

            ## prepare suspending
            send_(event)
            for key in Down:
                Ui.write(KeyCode, key, 0) # send key up events
            sendMod(NoMod)

            Down[::] = ToggleKeys

            suspending = True
            continue

        if char == UNDO:
            try: Down.remove(key) # key exceptionally not sent -> not down
            except: pass
            _undo()
            continue

        if char == CLEAR:
            Hist.clear()
            Matches = []
            send_(event)
            continue

        send_(event)
        addToHist(Matches, 0, char) # create abbr undo

        ## match against existing matches
        nMatches = []
        complete = []
        for a, i in Matches:
            if a[i] != char:
                continue

            i += 1
            if i == len(a):
                complete.append(a)
                continue

            nMatches.append((a, i))

        ## match against abbrs
        for abbrs in Abbrs:
            for a, b in abbrs:
                if a[0] == char:
                    if len(a) == 1:
                        complete.append(a)
                        continue

                    nMatches.append((a, 1))

        Matches = nMatches # update matches

        ## find complete with highest priority
        minD = len(Abbrs)
        minA, minB = None, None
        for a in complete:
            b, d = getBD(a)
            if d < minD:
                minD = d
                minA, minB = a, b

        if minD == len(Abbrs): # no complete
            continue

        ## drop matches with lower priority
        t = Matches
        Matches = []
        for match in t:
            a, i = match
            b, d = getBD(a)
            if minD < d:
                continue

            Matches.append(match)

        # if minA == minB: # nothing to do # wrong
            # continue

        ## perform abbr
        clear, write = undo(len(minA), chars=True)
        clear -= len(write)
        write = minB

        send(write)

        ## add to Hist
        addToHist([], clear, write) # matches=[] .. clear matches on abbr undo

        #print(time.time())

except:
    raise

finally:
    if suspended:
        try: dev.repeat = repeat
        except: pass

        try: dev.ungrab()
        except: pass

