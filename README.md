# AnyKey

applications/scripts implementing hierarchical abbreviations

## Why oh why

There are a large number of applications/macros/scripts available that allow the user to personalize their keyboard.
Most map keys to other keys, replace a certain sequence of characters by another sequence, and execute code or applications to perform certain tasks on a certain event.

Some time ago I switched from QWERTZ (DE) to Colemak (EN) and found that special characters like äöüÄÖÜß€ are hard to type.
A simple `ae -> ä`, `ue -> ü`, ... mapping was annoying due to frequent German words which contain ue (aktuell, neue, ...).

This was the birth of AnyKey.

## What the fancy

What I call 'hierarchical abbreviations' are abbreviations (sequence of characters are replaced by another sequence) that are part of a hierarchy.
Some are more important, thus further up, and some are less.
For example `eue -> eue` is more important than `ue -> ü` as it allows neue to be typed without the need to undo the ü.

There is more to AnyKey.
See features below.

## Featurette

* hierarchical abbreviations
* undo anytime
  * using any modifier+key combination
  * or any single modifier
* toggle suspend
* clear memory
* operates at low level (between dev and X)
  * needs root

## How to

This is probably the most difficult part.
First of all, if you don't use Linux, it won't work.
Secondly, the current configuration as found in the 'User Settings' section of the code is my own.
This means: QWERTY keyboard, Colemak, Esc triggers Capslock, Tab triggers Esc, Capslock triggers LCtrl, LCtrl triggers Tab, short Capslock triggers Backspace (referred to as UndoMod), hold Capslock after short Capslock triggers successive Backspace, ...

And finally, it's not easy to understand what the heck is going on in the script.
It grew over time and I really tried to keep it simple.
There is a section named 'print event'.
Uncomment those lines to get events printed to stdout.

There is also a short introduction to AnyKey with additional information at the very top of the file.

## Why so complicated

It was never my intention to publish AnyKey.
However, it was some effort and maybe there is someone like me who would appreciate it.

