# Adding an interface language

Shingle sites can be written in any language: the owner's facts and translations are data in
`business.json`. What ships with the plugin is the **interface text** (buttons, day names, "Open
now", the skip link…) for six languages: en, pt, es, fr, de, it. Any other language works too, but
its interface text falls back to English until someone adds a dictionary. That takes one file.

## 1. Copy the English dictionary (1 min)

```bash
cp skills/shingle/references/ui-strings/en.json skills/shingle/references/ui-strings/nl.json
```

The file name is the language code (`nl`, `pl`, `ja`…). Regional variants such as `pt-BR` use the
base file (`pt.json`) unless you add `pt-BR.json`; that file only needs the keys that differ.

## 2. Translate the values (8 min)

- Edit `_meta.language` (the code) and `_meta.native_name` (the language's own name: "Nederlands").
  The native name is what the language switcher shows.
- Translate every value; **keep the keys** and every `{placeholder}` exactly as written
  (`{time}`, `{day}`, `{what}`, `{name}`, `{address}`, `{language}`).
- `day_long.*` are used mid-sentence ("Closed · opens {day} …"): use the form that fits there
  (lower case in Portuguese, Spanish, French, Italian).
- `time.am` and `time.pm` are only shown on sites in countries that use a 12-hour clock.
- Keep strings short: they sit in buttons and a header.

## 3. Test (1 min)

```bash
python3 -m unittest discover -s skills/shingle/scripts/tests -t skills/shingle/scripts/tests
```

`test_ui_strings.py` checks that your file has exactly the keys of `en.json`, no empty values and
the same placeholders. Add your language to the list of expected files in that test.

## 4. Open a pull request

Say whether a native speaker has reviewed the file. Machine-drafted dictionaries are welcome, and
the `_meta.note` field says so until someone reviews them.

## Right-to-left languages

Arabic, Hebrew, Persian and Urdu are not supported yet: the templates use left/right CSS. The
validator warns when `languages` contains one. See the roadmap.
