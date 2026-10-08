# Day 0A — Your Toolkit: Terminal, Git, Node, Python & Reading Errors

> ⏱ **Time:** ~2 hours · 🎯 **Prereqs:** none — start here if you are new to programming · 🧩 **Difficulty:** ●○○○○

**Today you learn:** every later day says "open a terminal and run this". If you have never done
that, the first hour goes on errors that have nothing to do with AI. Today you learn the six
tools under every AI project: the terminal, folders and paths, Node.js and Python, packages,
git, and secret settings in a `.env` file. You also learn to read an error message calmly. You
finish with a small `env-check` script in both languages and an empty, correctly set up
StudyBuddy project.

> 📖 **Words you'll meet today**
>
> - **Terminal** — a window where you type commands to the computer instead of clicking.
> - **Path** — the address of a file or folder, like `C:\Users\you\studybuddy\.env`.
> - **Runtime** — the program that runs your code: Node.js runs JavaScript, Python runs Python.
> - **Package** — code someone else wrote that you download and use, like `dotenv`.
> - **Virtual environment** — a private folder of Python packages that belongs to one project.
> - **Git** — a tool that saves snapshots of your project so you can go back in time.
> - **Environment variable** — a named setting, like `GROQ_API_KEY`, that a program reads at start.
> - **Stack trace** — the list of places in your code that were running when an error happened.

> 🧪 **Every output on this page is real.** We ran each command on Windows 11 with Node.js
> 24.15.0, Python 3.14.4, npm 11.12.1 and git 2.53.0. We shortened long folder paths to
> `C:\Users\you\...` so they fit, and cut very long error lists (marked `…`). Your paths, dates
> and timings will differ.

---

## 1. The problem

Here is a beginner's first hour with Day 1 of an AI course. Every error message below is real
output from our test machine, shortened to the key line.

```text
PS> nod env-check.js
nod: The term 'nod' is not recognized as a name of a cmdlet, function, script file,
or executable program.

PS> node env-chek.js
Error: Cannot find module 'C:\Users\you\studybuddy\env-chek.js'

PS> node env-check.js
SyntaxError: Cannot use import statement outside a module

PS> python env_check.py
ModuleNotFoundError: No module named 'dotenv'

PS> git add .
PS> git commit -m "first try"        ← the .env file with the API key is now saved forever
```

Look at the five problems. A typo in a command. A typo in a file name. A project setting that
was never changed. A package installed in the wrong place. A secret saved by git. None of them
is about AI. All of them stop you.

The good news: each one has a short, exact cause. After today you will recognise all five on
sight and fix each one in under a minute.

### The real-life version

Think of a kitchen where you learn to cook.

| In the kitchen | In your computer | Today's section |
|---|---|---|
| Talking to the chef in words, not pointing at pictures | the **terminal** | 3.1 |
| Cupboard addresses: "top shelf, left door" | **folders and paths** | 3.2 |
| The oven. A pizza needs an oven, a salad needs a fridge | **runtimes**: Node.js for JS, Python for Python | 3.3 |
| Ingredients you buy from a shop | **packages** from npm and pip | 3.4 |
| One lunchbox per recipe, so flavours don't mix | a **virtual environment** per project | 3.4 |
| A photo album of the kitchen after each step | **git** commits | 3.5 |
| A locked drawer for the house keys | the **`.env` file** for API keys | 3.6 |
| A "do not photograph" sticker on that drawer | **`.gitignore`** | 3.5 |
| The smoke alarm, with a note saying which room | an **error message** and its **stack trace** | 3.7 |

A good cook knows the kitchen before the recipe. Today is the kitchen.

---

## 2. Mental model

### Who talks to whom

```
   YOU
    │  type a command, press Enter
    ▼
 ┌─────────── TERMINAL (PowerShell, bash, zsh) ───────────┐
 │ knows: the CURRENT FOLDER  and  ENVIRONMENT VARIABLES  │
 └─────┬────────────┬─────────────┬────────────┬──────────┘
       │ starts     │ starts      │ starts     │ starts
       ▼            ▼             ▼            ▼
     node         python         npm / pip      git
   runs .js     runs .py      download        saves
    files        files        packages       snapshots
       │            │             │
       └── read .env (with dotenv) ─┘  ← secrets come in here, never from your code
```

Each program the terminal starts gets **two things for free**: the current folder and a copy of
the environment variables. Keep that sentence in mind. It explains most beginner errors.

### What a finished project folder looks like

```
studybuddy/                  ← the project folder. Open your terminal HERE.
├── .git/                    ← git's photo album (hidden)
├── .gitignore               ← what git must never save
├── .env                     ← your real secrets          ✗ never saved by git
├── .env.example             ← the shape of .env, no secrets  ✓ saved by git
├── package.json             ← JS: settings + package list, "type": "module"
├── package-lock.json        ← JS: exact package versions
├── node_modules/            ← JS: downloaded packages     ✗ not saved, rebuild with npm install
├── requirements.txt         ← Python: package list
├── .venv/                   ← Python: private packages    ✗ not saved, rebuild with pip
├── env-check.js
└── env_check.py
```

### The tools, and how to check each one

| Tool | What it does | Check command | Our output |
|---|---|---|---|
| Node.js | runs JavaScript files | `node --version` | `v24.15.0` |
| npm | downloads JavaScript packages | `npm --version` | `11.12.1` |
| Python | runs Python files | `python --version` | `Python 3.14.4` |
| pip | downloads Python packages | `python -m pip --version` | `pip 26.0.1 from …\.venv\…` |
| git | saves snapshots of your project | `git --version` | `git version 2.53.0.windows.3` |
| VS Code | the editor where you write code | `code --version` | `1.139.1` (first line) |

This course needs **Node.js 20 or newer** and **Python 3.10 or newer**.

---

## 3. First principles

### 3.1 The terminal: talking to the computer in sentences

> 💬 **In plain words:** the terminal is a chat window with your computer. You type one command,
> press Enter, and it answers with text.

Why use it at all, when you could click? Three reasons. Every AI tool in this course is started
from a terminal. A typed command can be copied, shared and repeated exactly. And error messages
appear there, so that is where you fix things.

**Which terminal?**

| Your computer | Open this | It runs |
|---|---|---|
| Windows | **Terminal** or **PowerShell** from the Start menu | PowerShell |
| Windows, with Git installed | **Git Bash** | bash (same commands as macOS/Linux) |
| macOS | **Terminal** (in Applications → Utilities) | zsh |
| Linux | **Terminal** | bash |

Every command has the same shape: a **command name**, then **arguments** (extra words that say
what to work on). In `mkdir notes`, `mkdir` is the command and `notes` is the argument.

The line where you type is called the **prompt**. In this book, `PS>` means a PowerShell prompt
and `$` means a bash or zsh prompt. **Don't type the prompt itself**, only what comes after it.

**The ten commands you will use every day:**

| Job | PowerShell (Windows) | bash / zsh (macOS, Linux, Git Bash) |
|---|---|---|
| Where am I? | `pwd` | `pwd` |
| What is in this folder? | `ls` | `ls` (add `-a` to see names starting with `.`) |
| Go into a folder | `cd notes` | `cd notes` |
| Go up one folder | `cd ..` | `cd ..` |
| Make a folder | `mkdir notes` | `mkdir notes` |
| Make an empty file | `New-Item notes.txt` | `touch notes.txt` |
| Show what is in a file | `cat first.txt` | `cat first.txt` |
| Copy a file | `cp first.txt copy.txt` | `cp first.txt copy.txt` |
| Rename or move a file | `mv copy.txt renamed.txt` | `mv copy.txt renamed.txt` |
| Delete a file | `rm renamed.txt` | `rm renamed.txt` |
| Clear the screen | `cls` or `clear` | `clear` |

In PowerShell, most of these short names are **aliases**: nicknames for longer commands. We
checked: `ls` → `Get-ChildItem`, `cd` → `Set-Location`, `pwd` → `Get-Location`,
`cat` → `Get-Content`, `cp` → `Copy-Item`, `mv` → `Move-Item`, `rm` → `Remove-Item`. That is
why the same words work in both terminals.

Here is a real session in PowerShell:

```powershell
pwd
mkdir notes
cd notes
"hello from the terminal" > first.txt
ls
cat first.txt
```

```text
Path
----
C:\Users\you\projects\term-demo

    Directory: C:\Users\you\projects\term-demo\notes

Mode        LastWriteTime Length Name
----        ------------- ------ ----
-a--- 07/10/2026    13:15     25 first.txt

hello from the terminal
```

And the same session in Git Bash (macOS and Linux behave the same way):

```bash
pwd
mkdir notes
cd notes
echo "hello from the terminal" > first.txt
ls
cat first.txt
```

```text
/c/Users/you/projects/term-bash
first.txt
hello from the terminal
```

> 🪟 **Hidden files differ.** We made a `.env` file and a git repository in the same folder.
> PowerShell's `ls` showed `.env,.gitignore,app.js`, and needed `ls -Force` to also show
> `.git`. Bash's `ls` showed only `app.js`; `ls -a` showed `.env`, `.git` and `.gitignore` too.
> On macOS and Linux, any name starting with `.` is hidden by default.

> 💡 **Two keys that save hours.** Press **Tab** to finish a file or folder name for you, which
> stops typos. Press **↑** (up arrow) to bring back your last command.

### 3.2 Folders and paths

> 💬 **In plain words:** a path is an address. An absolute path starts from the top of the disk.
> A relative path starts from the folder you are in now.

Your terminal is always "standing" in one folder, called the **current folder** (or *working
directory*). `pwd` prints it. Every relative path is measured from there.

| Kind | Example (Windows) | Example (macOS/Linux) | Starts from |
|---|---|---|---|
| Absolute | `C:\Users\you\studybuddy\.env` | `/Users/you/studybuddy/.env` | the top of the disk |
| Relative | `.env` or `.\.env` | `.env` or `./.env` | the current folder |
| Parent | `..\notes` | `../notes` | one folder up |
| Home | `~\studybuddy` | `~/studybuddy` | your user folder |

Three short symbols do most of the work:

- `.` means **this folder**.
- `..` means **the folder above this one**.
- `~` means **your home folder** (`C:\Users\you` or `/Users/you`).

Windows writes `\` between folder names and macOS/Linux write `/`. PowerShell, Node.js and
Python on Windows also accept `/`, so you can use `/` in your code everywhere.

**When the path is wrong, the terminal says so.** We asked each terminal to go to a folder that
does not exist:

```text
PowerShell:  Set-Location: Cannot find path 'C:\Users\you\does-not-exist' because it does not exist.
bash:        bash: cd: ../../does-not-exist: No such file or directory
```

> ⚠️ **Spaces in paths need quotes.** `cd My Projects` is read as two separate words. Write
> `cd "My Projects"`. Better still: name your folders without spaces, like `my-projects`.

### 3.3 Runtimes: Node.js and Python

> 💬 **In plain words:** a `.js` file is a recipe. Node.js is the cook who reads it and does the
> work. A `.py` file needs a different cook: Python.

Your computer cannot run a `.js` or `.py` file by itself. You start a **runtime** and give it the
file name. That is all "running a file" means:

```bash
node hello.js        # Node.js reads hello.js and runs it
python hello.py      # Python reads hello.py and runs it
```

**Installing them** (not executed here, because installers are clicked, not typed, and their
screens change; check the current download page):

- **Node.js:** download the **LTS** version from <https://nodejs.org>. LTS means "long-term
  support": the stable version. It includes npm.
- **Python:** download from <https://www.python.org/downloads/>. On Windows, tick the box that
  adds Python to PATH if the installer shows one. On macOS, the command may be `python3`.
- **VS Code:** download from <https://code.visualstudio.com>. Open your project with
  **File → Open Folder**. Open a terminal inside VS Code with **Terminal → New Terminal**. It
  starts in your project folder, which avoids many path errors.
- **Git:** download from <https://git-scm.com>. On Windows it also installs Git Bash.

Then **close and reopen your terminal**, so it finds the new programs, and check the versions:

```bash
node --version
python --version
git --version
```

```text
v24.15.0
Python 3.14.4
git version 2.53.0.windows.3
```

If you see `v18.x` or `Python 3.9`, install a newer version before Day 1. If you see "not
recognized" or "command not found", the program is not installed, or the terminal was opened
before the install finished.

### 3.4 Packages: npm, pip and virtual environments

> 💬 **In plain words:** a package is a box of code someone else wrote. npm downloads boxes for
> JavaScript, pip downloads boxes for Python. A virtual environment is a private shelf, so one
> project's boxes don't fall onto another's.

Nobody writes everything from zero. To read a `.env` file you will use a small package called
`dotenv` (JavaScript) or `python-dotenv` (Python). Later days install LangChain the same way.

**JavaScript keeps packages inside the project.** `npm install dotenv` downloads into a
`node_modules/` folder **in the current folder**, and writes the package name into
`package.json`. Each project has its own `node_modules/`, so projects never fight. The price is
that you must run `npm install` in the right folder.

`package.json` is the project's ID card. You create it with `npm init -y`. Look closely at the
last line npm 11 wrote for us:

```json
{
  "name": "js",
  "version": "1.0.0",
  "description": "",
  "main": "index.js",
  "scripts": {
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "keywords": [],
  "author": "",
  "license": "ISC",
  "type": "commonjs"
}
```

> ⚠️ **npm 11 writes `"type": "commonjs"` for you.** Older guides say "add `"type": "module"`".
> With npm 11.12.1 you must **change** the existing line from `"commonjs"` to `"module"`.
> Otherwise every `import` line fails (§7, mistake 1). One command does it: `npm pkg set
> type=module`.

Why does that one word matter? JavaScript has two ways to load packages. The old way,
**CommonJS**, uses `require("dotenv")`. The modern way, **ES modules** (ESM), uses
`import "dotenv/config"`. Everything in this course uses `import`, so every project needs
`"type": "module"`. [Day 0B](day-00b-programming-for-ai.md) explains the difference properly.

**Python installs packages into the Python you run.** Without care, `pip install` puts packages
into the one Python on your computer, shared by every project. Two projects that need different
versions then break each other. A **virtual environment** (venv) fixes this. It is a folder,
usually `.venv`, with its own copy of Python and its own packages.

```powershell
python -m venv .venv               # 1. make the private folder (once per project)
.venv\Scripts\Activate.ps1         # 2. turn it on — Windows PowerShell
pip install python-dotenv          # 3. install INTO .venv
```

```bash
python3 -m venv .venv              # 1. macOS / Linux (python3)
source .venv/bin/activate          # 2. turn it on — macOS / Linux
source .venv/Scripts/activate      #    turn it on — Git Bash on Windows
pip install python-dotenv          # 3. install INTO .venv
```

We ran the Windows lines (PowerShell and Git Bash). The macOS/Linux lines are the standard
ones, but we did not execute them here, so check them on your system.

When the venv is on, your prompt starts with `(.venv)`. We checked what "on" really changes.
Before activation, `python` meant `C:\Users\you\AppData\Local\Microsoft\WindowsApps\python.exe`.
After activation it meant `C:\Users\you\projects\py\.venv\Scripts\python.exe`. Activation just
puts the venv's Python first in the list of places the terminal searches (§6.1).

> 🪟 **"Running scripts is disabled on this system".** On some Windows computers, PowerShell
> refuses to run `Activate.ps1`. We forced the strictest setting and got this real error.
>
> `.venv\Scripts\Activate.ps1: File …\Activate.ps1 cannot be loaded because running scripts is
> disabled on this system.`
>
> The usual fix is to run this once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
> We did not run it here, because our
> machine already used `RemoteSigned`, and activation worked with that setting.

> ⚠️ **Never install into "whatever Python happens to run".** Our test machine had
> `python-dotenv` installed in its main Python too. That hides bugs: a script works on your
> laptop and fails on a friend's. Always activate the venv, then install, then run.

### 3.5 Git: snapshots of your project

> 💬 **In plain words:** git takes a photo of your project folder whenever you ask. You can look
> at old photos and go back. `.gitignore` lists things that must never be in a photo.

Why bother on Day 0? Because you will break things. With git, "it worked an hour ago" becomes a
command, not a memory. And later, git is how you share code on GitHub. That is exactly where a
leaked API key becomes a real problem.

Git works in three steps:

```
  your folder ──git add──▶ the staging area ──git commit──▶ history (the photo album)
   (you edit)               ("these files go             (a saved snapshot, with
                              in the next photo")          a message and an ID)
```

Here is a real first session in a folder with `app.js` and a `.env` file:

```bash
git init
git status
```

```text
Initialized empty Git repository in C:/Users/you/projects/gitdemo/.git/
On branch main

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.env
	app.js
```

Git sees `.env`. If we ran `git add .` now, the key would go into the next photo. So **first**
we create `.gitignore`, a plain text file with one pattern per line:

```gitignore
.env
node_modules/
.venv/
__pycache__/
```

```bash
git status
```

```text
Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.gitignore
	app.js
```

`.env` has disappeared from the list. `git check-ignore -v .env` tells you which rule hides it:
`.gitignore:1:.env	.env`. Now it is safe to save:

```bash
git add .
git commit -m "First commit: app and .gitignore"
git status
```

```text
[main (root-commit) 304c9da] First commit: app and .gitignore
 2 files changed, 5 insertions(+)
 create mode 100644 .gitignore
 create mode 100644 app.js
On branch main
nothing to commit, working tree clean
```

If you try to add `.env` on purpose, git refuses (exit code 1):

```text
The following paths are ignored by one of your .gitignore files:
.env
hint: Use -f if you really want to add them.
```

> 🪟 **Harmless Windows warning.** On Windows we also saw
> `warning: in the working copy of 'app.js', LF will be replaced by CRLF the next time Git
> touches it`. Windows and macOS end lines with different invisible characters. Git converts
> them for you. You can ignore this warning.

> 💡 Our branch was called `main` because Git for Windows set that default. Some setups call
> the first branch `master`. Both work.

> 🔒 **`.gitignore` does not un-save a file.** It only stops *new* files from being added. We
> committed `.env` first and added `.gitignore` after: `git status` still showed ` M .env`,
> which means "tracked and changed". `git rm --cached .env` stopped tracking it. But
> `git show HEAD~1:.env` still printed the old key from history. **If a key was ever committed,
> treat it as stolen: delete it on the provider's website and create a new one.**

### 3.6 Environment variables and the `.env` file

> 💬 **In plain words:** an environment variable is a name and a value that a program can read
> when it starts. The `.env` file is a list of them, kept outside your code.

**Why not just write the key in the code?** Because code gets shared: on GitHub, in a help
request, in a screenshot. Anything inside the code travels with it. A key outside the code
stays on your computer.

Every program gets a **copy** of the terminal's environment variables when it starts. You can
set one for the current terminal only:

```powershell
$env:GROQ_API_KEY="gsk_pretend_key_for_testing"     # PowerShell
```

```bash
export GROQ_API_KEY=gsk_pretend_key_for_testing     # bash / zsh
```

We proved that it belongs to **one terminal only**. We set `DEMO_COLOUR=blue` in one
PowerShell, and a script there printed `blue`. A second, new PowerShell printed `(not set)`.

Typing keys every time you open a terminal is tiring and easy to get wrong. So we write them in
a file named `.env` in the project folder:

```bash
# .env — one NAME=value per line. No spaces around "=". No quotes needed.
GROQ_API_KEY=gsk_pretend_key_for_testing
```

The `.env` file does nothing by itself. A small package reads it when your program starts and
copies each line into the environment:

- JavaScript: `import "dotenv/config";` (package `dotenv`, version 18.0.6 here)
- Python: `from dotenv import load_dotenv` then `load_dotenv()` (package `python-dotenv`, 1.2.4)

To get real keys from Groq and Google, follow **[SETUP.md](../SETUP.md)**. Today we use a fake
value, `gsk_pretend_key_for_testing`, so you can practise with no account at all.

**`.env.example`: the shape without the secrets.** Your teammate needs to know *which* variables
to set, but not your values. So you commit a second file, `.env.example`, with empty values:

```bash
# .env.example — committed to git. Copy it to .env and fill in your own values.
GROQ_API_KEY=
GOOGLE_API_KEY=
```

### 3.7 Reading an error message

> 💬 **In plain words:** an error message answers three questions: what went wrong, where, and
> how the program got there. Find those three answers before you change anything.

Errors look scary because they are long. But most of the text is a list of places, and you
only need three pieces:

1. **The error type and message**, like `TypeError: Cannot read properties of undefined`.
2. **The first line that points at *your* file**, like `buggy.js:8` or `buggy.py, line 8`.
3. **The code on that line.** Both languages print it for you.

Here is the same bug in both languages. We forgot to `return` the settings from a function:

```js
// buggy.js
function loadSettings() {
  const settings = { course: "StudyBuddy", day: 0 };
  // BUG: we forgot to write `return settings;`
}

function printReport(settings) {
  console.log("Course:", settings.course);
}

const settings = loadSettings();
printReport(settings);
```

```python
# buggy.py
def load_settings():
    settings = {"course": "StudyBuddy", "day": 0}
    # BUG: we forgot to write `return settings`


def print_report(settings):
    print("Course:", settings["course"])


settings = load_settings()
print_report(settings)
```

**Node.js puts the important part at the top:**

```text
file:///C:/Users/you/projects/js/buggy.js:8                        ← ② file and line
  console.log("Course:", settings.course);                         ← ③ the code
                                  ^

TypeError: Cannot read properties of undefined (reading 'course')  ← ① type + message
    at printReport (file:///C:/Users/you/projects/js/buggy.js:8:35)   ← newest call FIRST
    at file:///C:/Users/you/projects/js/buggy.js:12:1                ← who called it
    at ModuleJob.run (node:internal/modules/esm/module_job:437:25)    ← Node's own code: skip
    at async node:internal/modules/esm/loader:639:26
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:101:5)

Node.js v24.15.0
```

**Python puts the important part at the bottom:**

```text
Traceback (most recent call last):                     ← "newest call LAST"
  File "C:\Users\you\projects\py\buggy.py", line 12, in <module>
    print_report(settings)
    ~~~~~~~~~~~~^^^^^^^^^^
  File "C:\Users\you\projects\py\buggy.py", line 8, in print_report   ← ② file and line
    print("Course:", settings["course"])                               ← ③ the code
                     ~~~~~~~~^^^^^^^^^^
TypeError: 'NoneType' object is not subscriptable      ← ① type + message: READ THIS FIRST
```

| | Node.js | Python |
|---|---|---|
| Where is the error type? | near the **top**, the line starting `SomethingError:` | the **last line** |
| Order of the call list | newest call **first** | newest call **last** |
| Lines to skip | `node:internal/...` | files inside `site-packages` or `<frozen ...>` |
| What "nothing" is called | `undefined` | `None` (type `NoneType`) |

Now translate. "Cannot read properties of **undefined**" and "**NoneType** is not
subscriptable" both mean the same thing: *you used a value that is empty*. Where did it come
from? The line that called `printReport(settings)` passed `settings`, which came from
`loadSettings()`. That function returns nothing. The bug is one line above the crash, which is
very common. **The line where it crashes is not always the line that is wrong.**

> 💡 **Long traces are mostly other people's code.** When a library crashes, Python may print
> twenty frames from inside `site-packages`. Read the last line first, then search upwards for
> the first frame in *your* file. §7 mistake 5 shows a real 30-line trace that comes from one
> bad file.

### 3.8 Asking for help well

> 💬 **In plain words:** a good question includes what you ran, what you expected, what
> happened, and your versions. It never includes your API key.

People help quickly when they can see the problem without guessing. Use this template:

```text
**What I ran:**      node env-check.js   (in C:\Users\you\studybuddy)
**What I expected:** "All good. You are ready for Day 1!"
**What happened:**   (paste the FULL error as text, not a photo)
**Versions:**        Node v24.15.0, npm 11.12.1, Windows 11
**What I tried:**    I ran npm install again. Same error.
```

Four rules:

1. **Paste text, not a screenshot.** Others can copy and search text.
2. **Paste the whole error,** from the first line to the last.
3. **Search the exact error line first.** Put the message in quotes, without your own paths.
4. **Never paste `.env` or a key.** Our `env-check` script prints the *length* of a key, never
   the key. That is enough to show it is set.

---

## 4. Code — JavaScript

We build one small tool in four steps: `env-check.js`. It checks your Node.js version and your
`.env` file, then prints a friendly report. You will run it before every week of this course.

### 4.1 Check Node.js and run your first file

Make a folder, go into it, and check Node.js:

```bash
mkdir env-check-js
cd env-check-js
node --version
```

```text
v24.15.0
```

Open the folder in VS Code (**File → Open Folder**) and create a file named `hello.js`:

```js
// hello.js — your first JavaScript file
console.log("Hello from Node.js!");
console.log("Node version:", process.version);
console.log("2 + 3 =", 2 + 3);
```

Run it from the terminal:

```bash
node hello.js
```

```text
Hello from Node.js!
Node version: v24.15.0
2 + 3 = 5
```

`console.log` prints a line. `process` is an object that Node.js gives every program: facts
about the running program, like its version.

### 4.2 Make it a project: `package.json`, ESM and `dotenv`

```bash
npm init -y                  # create package.json
npm pkg set type=module      # change "type" from "commonjs" to "module"
npm install dotenv           # download dotenv into node_modules/
```

```text
added 1 package, and audited 2 packages in 4s

1 package is looking for funding
  run `npm fund` for details

found 0 vulnerabilities
```

Your `package.json` now ends like this:

```json
  "license": "ISC",
  "type": "module",
  "dependencies": {
    "dotenv": "^18.0.6"
  }
}
```

`^18.0.6` means "version 18.0.6 or any newer 18.x". The exact version is written in
`package-lock.json`, so a teammate's `npm install` gets the same one.

### 4.3 env-check, version 1: which Node.js is running?

```js
// env-check.js — version 1: which Node.js is running this file?
const MIN_NODE = 20;

const version = process.version;                           // e.g. "v24.15.0"
const major = Number(process.versions.node.split(".")[0]); // e.g. 24

console.log("StudyBuddy env-check (JavaScript)");
console.log("  Node.js version:", version);
console.log("  Operating system:", process.platform);
console.log("  Folder I am running in:", process.cwd());

if (major >= MIN_NODE) {
  console.log(`  ✅ Node.js ${major} is new enough (need ${MIN_NODE}+)`);
} else {
  console.log(`  ❌ Node.js ${major} is too old (need ${MIN_NODE}+)`);
}
```

```text
StudyBuddy env-check (JavaScript)
  Node.js version: v24.15.0
  Operating system: win32
  Folder I am running in: C:\Users\you\projects\env-check-js
  ✅ Node.js 24 is new enough (need 20+)
```

`process.cwd()` is the **current working directory**: the same folder `pwd` prints. Keep an eye
on it. It decides where `dotenv` looks for `.env` (§6.3).

### 4.4 Version 2: is the key set? (without showing it)

```js
// env-check.js — version 2: is the key set? (without showing it)
const name = "GROQ_API_KEY";
const value = process.env[name];   // undefined if the variable does not exist

if (value) {
  console.log(`✅ ${name} is set (${value.length} characters, value hidden)`);
} else {
  console.log(`❌ ${name} is not set`);
}
```

`process.env` holds every environment variable as text. Run it twice: once plain, once with the
variable set for this terminal (§3.6):

```text
$ node env-check.js
❌ GROQ_API_KEY is not set

$ export GROQ_API_KEY=gsk_pretend_key_for_testing      (PowerShell: $env:GROQ_API_KEY="...")
$ node env-check.js
✅ GROQ_API_KEY is set (27 characters, value hidden)
```

> 🔒 **Print facts about a secret, never the secret.** "Set, 27 characters" is enough to debug.
> The key itself should never appear on screen, in a log or in a screenshot.

### 4.5 Version 3: load the `.env` file

Close and reopen the terminal, so the variable from §4.4 is gone. Create a file named `.env`
in the project folder, with VS Code (**File → New File**):

```bash
GROQ_API_KEY=gsk_pretend_key_for_testing
```

Add **one line** at the very top of `env-check.js`:

```js
// env-check.js — version 3: load the .env file first
import "dotenv/config";            // reads .env and copies each line into process.env

const name = "GROQ_API_KEY";
const value = process.env[name];

if (value) {
  console.log(`✅ ${name} is set (${value.length} characters, value hidden)`);
} else {
  console.log(`❌ ${name} is not set`);
}
```

```text
without .env:   ❌ GROQ_API_KEY is not set
with .env:      ✅ GROQ_API_KEY is set (27 characters, value hidden)
```

> 📦 **dotenv may print a line.** With `import "dotenv/config"`, dotenv 18.0.6 printed nothing.
> With `dotenv.config()` it printed `◇ injected env (1) from .env`. That line is harmless. It
> only tells you how many variables it loaded. Pass `{ quiet: true }` to hide it.

### 4.6 The final env-check: a friendly report and an exit code

The final version checks several variables, explains each problem in plain words, and tells the
terminal whether everything passed:

```js
// env-check.js — is this computer ready for the course?
import "dotenv/config";            // copy .env into process.env (must come first)

const MIN_NODE = 20;
const REQUIRED = ["GROQ_API_KEY"];
const OPTIONAL = ["GOOGLE_API_KEY"];

// Describe a variable WITHOUT ever printing its value.
function check(name) {
  const value = process.env[name];
  if (!value) return { ok: false, note: "missing" };
  if (value !== value.trim()) return { ok: false, note: "has a space at the start or end" };
  return { ok: true, note: `set (${value.length} characters, hidden)` };
}

const major = Number(process.versions.node.split(".")[0]);
const todo = [];

console.log("StudyBuddy env-check (JavaScript)");
console.log(`  Node.js         ${process.version}  ${major >= MIN_NODE ? "✅" : "❌"}`);
if (major < MIN_NODE) todo.push(`Install Node.js ${MIN_NODE} or newer`);

for (const name of REQUIRED) {
  const r = check(name);
  console.log(`  ${name.padEnd(15)} ${r.ok ? "✅" : "❌"} ${r.note}`);
  if (!r.ok) todo.push(`Fix ${name} in your .env file (see SETUP.md)`);
}
for (const name of OPTIONAL) {
  const r = check(name);
  console.log(`  ${name.padEnd(15)} ${r.ok ? "✅" : "➖"} ${r.note} (optional)`);
}

if (todo.length > 0) {
  console.log("\nNot ready yet. Please fix:");
  todo.forEach((item, i) => console.log(`  ${i + 1}. ${item}`));
  process.exit(1);                 // exit code 1 = "something is wrong"
}
console.log("\nAll good. You are ready for Day 1!");
```

With the `.env` file:

```text
StudyBuddy env-check (JavaScript)
  Node.js         v24.15.0  ✅
  GROQ_API_KEY    ✅ set (27 characters, hidden)
  GOOGLE_API_KEY  ➖ missing (optional)

All good. You are ready for Day 1!
```

Without it (we renamed `.env` for a moment):

```text
StudyBuddy env-check (JavaScript)
  Node.js         v24.15.0  ✅
  GROQ_API_KEY    ❌ missing
  GOOGLE_API_KEY  ➖ missing (optional)

Not ready yet. Please fix:
  1. Fix GROQ_API_KEY in your .env file (see SETUP.md)
```

And with a quoted value that ends in a space, `GROQ_API_KEY="gsk_pretend_key_for_testing "`:

```text
  GROQ_API_KEY    ❌ has a space at the start or end
```

That check matters. A key with a hidden space gets rejected by the provider, and the error you
see there does not mention the space.

**Exit codes.** Every program ends with a number. `0` means success; anything else means a
problem. Other tools, like test runners, read this number. You can read it too:

```powershell
node env-check.js; $LASTEXITCODE        # PowerShell → 0 with .env, 1 without
```

```bash
node env-check.js; echo $?              # bash / zsh  → 0 with .env, 1 without
```

---

## 5. Code — Python

The same tool, the same four steps: `env_check.py`. Python file names use `_`, not `-`, because
Python cannot `import` a name that contains `-`.

### 5.1 Check Python and run your first file

```bash
mkdir env-check-py
cd env-check-py
python --version
```

```text
Python 3.14.4
```

Create `hello.py`:

```python
# hello.py — your first Python file
import platform

print("Hello from Python!")
print("Python version:", platform.python_version())
print("2 + 3 =", 2 + 3)
```

```bash
python hello.py
```

```text
Hello from Python!
Python version: 3.14.4
2 + 3 = 5
```

`import platform` loads a module that ships with Python. You don't need to install it.

### 5.2 Make it a project: a venv, `python-dotenv` and `requirements.txt`

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install python-dotenv
pip freeze > requirements.txt
```

`pip list` inside the venv shows only what this project installed:

```text
Package       Version
------------- -------
pip           26.0.1
python-dotenv 1.2.4
```

`pip freeze > requirements.txt` writes the list into a file. Ours contains one line:

```text
python-dotenv==1.2.4
```

That file is Python's version of the `dependencies` block in `package.json`. A teammate runs
`pip install -r requirements.txt` inside their own venv and gets the same packages. We tested
exactly that with a fresh copy of the project.

> 💡 pip may also print `[notice] A new release of pip is available`. That is information, not
> an error. You can ignore it.

### 5.3 env_check, version 1: which Python is running?

```python
# env_check.py — version 1: which Python is running this file?
import os
import platform
import sys

MIN_PYTHON = (3, 10)

print("StudyBuddy env-check (Python)")
print("  Python version:", platform.python_version())
print("  Operating system:", sys.platform)
print("  Folder I am running in:", os.getcwd())
print("  Inside a virtual environment:", sys.prefix != sys.base_prefix)

if sys.version_info >= MIN_PYTHON:
    print("  ✅ Python is new enough (need 3.10+)")
else:
    print("  ❌ Python is too old (need 3.10+)")
```

```text
StudyBuddy env-check (Python)
  Python version: 3.14.4
  Operating system: win32
  Folder I am running in: C:\Users\you\projects\env-check-py
  Inside a virtual environment: True
  ✅ Python is new enough (need 3.10+)
```

`sys.prefix != sys.base_prefix` is how a Python program can tell that it runs inside a venv.
Inside, `sys.prefix` points at `.venv`; outside, both values point at the main Python.

### 5.4 Version 2: is the key set? (without showing it)

```python
# env_check.py — version 2: is the key set? (without showing it)
import os

name = "GROQ_API_KEY"
value = os.environ.get(name)   # None if the variable does not exist

if value:
    print(f"✅ {name} is set ({len(value)} characters, value hidden)")
else:
    print(f"❌ {name} is not set")
```

```text
$ python env_check.py
❌ GROQ_API_KEY is not set

$ export GROQ_API_KEY=gsk_pretend_key_for_testing      (PowerShell: $env:GROQ_API_KEY="...")
$ python env_check.py
✅ GROQ_API_KEY is set (27 characters, value hidden)
```

`os.environ.get(name)` returns `None` when the name is missing. `os.environ[name]` would crash
with a `KeyError` instead. For a checker, `.get` is the polite choice.

### 5.5 Version 3: load the `.env` file

Use the same `.env` file as in §4.5. Then add two lines:

```python
# env_check.py — version 3: load the .env file first
import os

from dotenv import load_dotenv

found = load_dotenv()          # reads .env and copies each line into os.environ
print("load_dotenv() returned:", found)

name = "GROQ_API_KEY"
value = os.environ.get(name)

if value:
    print(f"✅ {name} is set ({len(value)} characters, value hidden)")
else:
    print(f"❌ {name} is not set")
```

```text
without .env:   load_dotenv() returned: False
                ❌ GROQ_API_KEY is not set
with .env:      load_dotenv() returned: True
                ✅ GROQ_API_KEY is set (27 characters, value hidden)
```

Notice the package names. You install **`python-dotenv`**, but you import **`dotenv`**. That
surprises many people, so remember it.

### 5.6 The final env_check: a friendly report and an exit code

Python can check one extra thing that JavaScript doesn't need: is the venv active?

```python
# env_check.py — is this computer ready for the course?
import os
import platform
import sys

from dotenv import load_dotenv

load_dotenv()                      # copy .env into os.environ (must come first)

MIN_PYTHON = (3, 10)
REQUIRED = ["GROQ_API_KEY"]
OPTIONAL = ["GOOGLE_API_KEY"]


def check(name):
    """Describe a variable WITHOUT ever printing its value."""
    value = os.environ.get(name)
    if not value:
        return False, "missing"
    if value != value.strip():
        return False, "has a space at the start or end"
    return True, f"set ({len(value)} characters, hidden)"


todo = []
py_ok = sys.version_info >= MIN_PYTHON
in_venv = sys.prefix != sys.base_prefix

print("StudyBuddy env-check (Python)")
print(f"  Python          {platform.python_version()}  {'✅' if py_ok else '❌'}")
if not py_ok:
    todo.append("Install Python 3.10 or newer")
print(f"  Virtual env     {'✅ active' if in_venv else '❌ not active'}")
if not in_venv:
    todo.append("Activate your virtual environment (.venv)")

for name in REQUIRED:
    ok, note = check(name)
    print(f"  {name:<15} {'✅' if ok else '❌'} {note}")
    if not ok:
        todo.append(f"Fix {name} in your .env file (see SETUP.md)")
for name in OPTIONAL:
    ok, note = check(name)
    print(f"  {name:<15} {'✅' if ok else '➖'} {note} (optional)")

if todo:
    print("\nNot ready yet. Please fix:")
    for i, item in enumerate(todo, start=1):
        print(f"  {i}. {item}")
    sys.exit(1)                    # exit code 1 = "something is wrong"
print("\nAll good. You are ready for Day 1!")
```

Inside the venv, with `.env`:

```text
StudyBuddy env-check (Python)
  Python          3.14.4  ✅
  Virtual env     ✅ active
  GROQ_API_KEY    ✅ set (27 characters, hidden)
  GOOGLE_API_KEY  ➖ missing (optional)

All good. You are ready for Day 1!
```

After `deactivate` (the venv is off), with the same `.env`:

```text
StudyBuddy env-check (Python)
  Python          3.14.4  ✅
  Virtual env     ❌ not active
  GROQ_API_KEY    ✅ set (27 characters, hidden)
  GOOGLE_API_KEY  ➖ missing (optional)

Not ready yet. Please fix:
  1. Activate your virtual environment (.venv)
```

Why did it run at all, outside the venv? Because our main Python *also* had `python-dotenv`
installed. That is exactly the hidden bug from §3.4. On a clean computer, the same command
crashes with `ModuleNotFoundError: No module named 'dotenv'`. The venv check catches the mistake
on either computer.

The exit code works the same way: `sys.exit(1)` ends with code 1, and a normal finish is 0.

### 5.7 The JS ↔ Python translation for today

| Idea | JavaScript (Node.js) | Python |
|---|---|---|
| Run a file | `node env-check.js` | `python env_check.py` |
| Check the version | `node --version` | `python --version` |
| Package tool | `npm` | `pip` (use `python -m pip` when unsure) |
| Project package list | `package.json` → `dependencies` | `requirements.txt` |
| Exact versions | `package-lock.json` (automatic) | `pip freeze > requirements.txt` |
| Where packages go | `node_modules/` in the project | `.venv/` after you activate it |
| Install everything | `npm install` | `pip install -r requirements.txt` |
| Isolation | automatic, per folder | manual: `python -m venv .venv` + activate |
| Module setting | `"type": "module"` in `package.json` | none needed |
| Load `.env` | `import "dotenv/config";` | `from dotenv import load_dotenv` + `load_dotenv()` |
| Package name vs import name | `dotenv` / `dotenv` | `python-dotenv` / `dotenv` |
| Read a variable | `process.env.NAME` → `undefined` if missing | `os.environ.get("NAME")` → `None` if missing |
| Runtime version | `process.version` | `platform.python_version()` |
| Current folder | `process.cwd()` | `os.getcwd()` |
| Which program is running | `process.execPath` | `sys.executable` |
| Exit with an error | `process.exit(1)` | `sys.exit(1)` |
| "Nothing" value | `undefined` / `null` | `None` |
| Where the error type is | top of the trace | last line of the trace |
| Where `.env` is searched | the current folder only | from the script's folder upwards |

---

## 6. Under the hood

### 6.1 How the terminal finds `node` and `python`: the PATH

When you type `python`, the terminal does not search the whole disk. It reads an environment
variable called **`PATH`**: a list of folders. It looks in each folder, in order, and runs the
**first** match.

You can ask which file it will run. `where.exe python` (Windows) or `which python` (macOS,
Linux, Git Bash) lists the matches. On our machine, `where.exe python` found **two**:

```text
C:\Users\you\AppData\Local\Microsoft\WindowsApps\python.exe
C:\Users\you\AppData\Local\Python\bin\python.exe
```

The first one wins. Activating a venv does one main thing: it puts `.venv\Scripts` (or
`.venv/bin`) at the **front** of `PATH`. `deactivate` puts `PATH` back. This also means you can
skip activation and call the venv's Python by its path. We ran
`.venv\Scripts\python.exe env_check.py` without activating, and the script reported
`Virtual env ✅ active`.

"Not recognized" or "command not found" simply means: no folder in `PATH` had that name. Either
the program is not installed, the name has a typo, or the terminal was opened before the install
changed `PATH`.

### 6.2 What a venv really is

A venv is an ordinary folder. Ours contained `Include`, `Lib`, `Scripts` and a small text file,
`pyvenv.cfg`:

```text
home = C:\Users\you\AppData\Local\Python\pythoncore-3.14-64
include-system-site-packages = false
version = 3.14.4
executable = C:\Users\you\AppData\Local\Python\pythoncore-3.14-64\python.exe
```

`Scripts` holds a `python.exe` for the venv, plus `pip.exe` and the activation scripts.
Packages go into `Lib\site-packages`. `include-system-site-packages = false` is the important
line: this Python cannot see packages from the main Python. That is the isolation.

Because a venv is just files, you never copy it or commit it. You rebuild it from
`requirements.txt`. That is why `.venv/` is in `.gitignore`.

### 6.3 Where `.env` is searched, and who wins

We ran both version-3 scripts from the **parent** folder (`node js/env-check.js` and
`python py/env_check.py`). The `.env` file sat next to the scripts:

```text
JavaScript:  ❌ GROQ_API_KEY is not set
Python:      load_dotenv() returned: True
             ✅ GROQ_API_KEY is set (27 characters, value hidden)
```

They differ. JavaScript's `dotenv` looks for `.env` in the **current folder** (`process.cwd()`).
Python's `load_dotenv()` starts in the **script's folder** and walks upwards. The safe habit
for both: **open your terminal in the project folder and run from there.**

What if a variable is set in the terminal **and** in `.env`? We set `GROQ_API_KEY=from_shell` in
the terminal and `GROQ_API_KEY=from_dotenv_file` in `.env`. Both libraries printed `from_shell`.
**The real environment wins; `.env` only fills gaps.** That is useful: a server can set real
values and ignore any `.env` that was copied there by mistake.

How each line of `.env` is read (identical results in both libraries):

| Line in `.env` | Value your program gets |
|---|---|
| `# a comment line is ignored` | (nothing) |
| `UNQUOTED_SPACES=   abc   ` | `"abc"`: spaces around it are removed |
| `QUOTED_SPACE="abc "` | `"abc "`: inside quotes, the space stays |
| `WITH_COMMENT=abc # trailing comment` | `"abc"` |
| `EMPTY=` | `""`: set, but empty |

A `.env` saved with Windows line endings (CRLF) also worked in both: the key still had 27
characters.

### 6.4 Node.js can read `.env` by itself now

Node.js has a built-in option. On Node 24.15.0 we ran `node --env-file=.env env-check.js`, and
the key was set with no `dotenv` package. `process.loadEnvFile()` also worked from inside code.
One sharp edge: with a missing file, `node --env-file=missing.env` stopped with
`missing.env: not found` and exit code 9. `--env-file-if-exists` continued without it.

This course still uses `dotenv`, because the same line works on every Node version the course
supports and it mirrors Python's `python-dotenv`. If you prefer the built-in option, it is a
fine choice; check that your Node version has it.

### 6.5 Git's three places, and why history keeps secrets

```
  working folder        staging area          history (.git)
  ──────────────        ────────────          ──────────────
  files you edit  ─add─▶ next snapshot  ─commit─▶ snapshot 1 ─ snapshot 2 ─ snapshot 3
                                                    ▲
                                                    └── every old snapshot can be read again
```

A commit is a full, permanent snapshot. Deleting a file later creates a *new* snapshot without
it, but the old one still exists. That is why `git show HEAD~1:.env` could print our old key
(§3.5). When code is pushed to GitHub, the whole history goes with it. Automated programs scan
public code for keys, so a leaked key must be deleted and replaced on the provider's website,
not just removed from the code.

---

## 7. Common mistakes

### ❌ 1. Leaving `"type": "commonjs"` in `package.json`

npm 11 writes `"type": "commonjs"` when you run `npm init -y`. Then the first `import` fails:

```text
(node:10392) Warning: Failed to load the ES module: C:\Users\you\projects\js\env-check.js.
Make sure to set "type": "module" in the nearest package.json file or use the .mjs extension.
C:\Users\you\projects\js\env-check.js:2
import "dotenv/config";
^^^^^^

SyntaxError: Cannot use import statement outside a module
```

❌ `"type": "commonjs"` (or a hand-written `require` example copied from an old blog post)

✅ `npm pkg set type=module`, or edit the line to `"type": "module"`.

> 📦 If `package.json` has **no** `"type"` line at all, Node 24.15.0 did not crash. It printed
> `[MODULE_TYPELESS_PACKAGE_JSON] Warning: … Reparsing as ES module because module syntax was
> detected. This incurs a performance overhead.` and then ran the file. Older Node versions may
> fail instead. Set the line explicitly, and the question never comes up.

### ❌ 2. Using `require` in a `"type": "module"` project

The opposite mistake. Old examples use `require`, which does not exist in ES modules:

```js
// ❌ in a "type": "module" project
const dotenv = require("dotenv");
dotenv.config();
```

```text
ReferenceError: require is not defined in ES module scope, you can use import instead
This file is being treated as an ES module because it has a '.js' file extension and
'C:\Users\you\projects\breakjs\package.json' contains "type": "module". To treat it as a
CommonJS script, rename it to use the '.cjs' file extension.
```

```js
// ✅
import "dotenv/config";
```

Notice how helpful that message is. It says what is wrong, why, and two ways to fix it. Many
errors do this. Read the whole message before you search the web.

### ❌ 3. Installing or running Python outside the venv

```text
❌  pip install python-dotenv      (venv not active: goes into the main Python)
    python env_check.py           (later, in a new terminal, venv not active)

ModuleNotFoundError: No module named 'dotenv'
```

✅ Activate first, every time you open a new terminal. Check the prompt says `(.venv)`, or run
`python -c "import sys; print(sys.executable)"` and look for `.venv` in the path.

### ❌ 4. PowerShell refuses to run `Activate.ps1`

```text
.venv\Scripts\Activate.ps1: File …\.venv\Scripts\Activate.ps1 cannot be loaded because running
scripts is disabled on this system.
```

✅ Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again. (Not
executed here. Our machine already used `RemoteSigned`, and activation worked with it.) Or skip
activation and call `.venv\Scripts\python.exe` directly (§6.1).

### ❌ 5. Creating `.env` with `>` in Windows PowerShell 5.1

Windows ships two PowerShells: the old **Windows PowerShell 5.1** (blue window) and the newer
**PowerShell 7**. We ran the same line in both:

```powershell
"GROQ_API_KEY=gsk_pretend_key_for_testing" > .env
```

| Made by | File encoding | JavaScript `dotenv` | Python `python-dotenv` |
|---|---|---|---|
| Windows PowerShell 5.1 | **UTF-16** | ❌ `GROQ_API_KEY is not set` (no error!) | 💥 crash, 30-line trace |
| PowerShell 7.6 | plain text | ✅ set | ✅ set |

The Python trace is long, but the method from §3.7 works. The last line says what happened:

```text
  File "C:\Users\you\projects\utf16\env_check_v3.py", line 6, in <module>      ← your line
    found = load_dotenv()          # reads .env and copies each line into os.environ
  File "C:\Users\you\projects\py\.venv\Lib\site-packages\dotenv\main.py", line 435, in load_dotenv
  …  (eight more frames inside site-packages and <frozen codecs>)  …
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

Your only line is `load_dotenv()`. The last line says the file is not UTF-8 text. So the
problem is the **file**, not the code.

✅ Create and edit `.env` in VS Code, which saves plain UTF-8 text. Or use PowerShell 7.

### ❌ 6. Running from the wrong folder

```text
$ cd ..
$ node js/env-check.js
❌ GROQ_API_KEY is not set          ← .env exists, but in js/, not in the current folder
```

✅ `cd` into the project folder first, then run. `pwd` tells you where you are. (Python found
the file in this test, because `load_dotenv()` searches from the script's folder; §6.3.)

### ❌ 7. Adding `.gitignore` after `.env` was committed

✅ `.gitignore` first, then `git add`. If it already happened: `git rm --cached .env`, commit,
**and replace the key** on the provider's website, because history still holds it (§3.5).

### ❌ 8. Printing the key to "check" it

```js
console.log(process.env.GROQ_API_KEY);        // ❌ now it is in your terminal history and screenshots
```

```python
print(os.environ["GROQ_API_KEY"])             # ❌ same problem
```

✅ Print whether it is set and how long it is, like `env-check` does. Never paste `.env` into a
help request, a chat or an issue.

### ❌ 9. Emoji crash when Python output is redirected on Windows

We sent `env_check.py`'s output into another program (`python env_check.py | cat`):

```text
StudyBuddy env-check (Python)
Traceback (most recent call last):
  File "C:\Users\you\projects\py\env_check.py", line 30, in <module>
    print(f"  Python          {platform.python_version()}  {'\u2705' if py_ok else '\u274c'}")
  …
UnicodeEncodeError: 'charmap' codec can't encode character '\u2705' in position 26: character
maps to <undefined>
```

The first line printed; the line with ✅ crashed. On Windows, redirected output used an old
character set (`cp1252`) with no emoji.

✅ Set `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`) in the terminal. With either one, the same
command printed the emoji correctly.

### ❌ 10. Typing terminal commands inside Python or Node

If you type `python` or `node` alone, you enter an interactive mode (a **REPL**) with a `>>>` or
`>` prompt. Terminal commands don't work there. We piped the mistake in:

```text
>>> pip install python-dotenv
  File "<stdin>", line 1
    pip install python-dotenv
        ^^^^^^^
SyntaxError: invalid syntax

> npm install dotenv
npm should be run outside of the Node.js REPL, in your normal shell.
(Press Ctrl+D to exit.)
```

✅ Leave with `exit()` (Python) or **Ctrl+D** / `.exit` (Node), then run the command. Your
interactive screen may look slightly different from our piped output.

---

## 8. Exercises

### Exercise 1 — Prove it: which program, which folder, which variables? ●○○○○

Write a four-line script, `where-am-i`, in both languages. It prints: the full path of the
program running it, its version, the current folder, and the value of a harmless variable
called `DEMO_COLOUR` (or `(not set)`).

Then prove three things to yourself:

1. Run the Python version with the venv **off**, then **on**. Does line 1 change?
2. Set `DEMO_COLOUR=blue` in one terminal and run it. Open a **new** terminal and run it again.
3. Run it from the project folder, then `cd ..` and run it again with a path. Which line
   changes?

<details>
<summary>✅ Solution</summary>

```js
// where-am-i.js — four facts about the program that is running
console.log("1. Program running me:", process.execPath);
console.log("2. Its version:       ", process.version);
console.log("3. Current folder:    ", process.cwd());
console.log("4. DEMO_COLOUR is:    ", process.env.DEMO_COLOUR ?? "(not set)");
```

```python
# where_am_i.py — four facts about the program that is running
import os
import platform
import sys

print("1. Program running me:", sys.executable)
print("2. Its version:       ", platform.python_version())
print("3. Current folder:    ", os.getcwd())
print("4. DEMO_COLOUR is:    ", os.environ.get("DEMO_COLOUR", "(not set)"))
```

Our results, in PowerShell after `$env:DEMO_COLOUR="blue"`:

```text
1. Program running me: C:\Program Files\nodejs\node.exe
2. Its version:        v24.15.0
3. Current folder:     C:\Users\you\projects\js
4. DEMO_COLOUR is:     blue

1. Program running me: C:\Users\you\AppData\Local\Python\pythoncore-3.14-64\python.exe   ← venv off
1. Program running me: C:\Users\you\projects\py\.venv\Scripts\python.exe               ← venv on
```

In a **new** PowerShell window, line 4 said `4. DEMO_COLOUR is:     (not set)`. In bash,
`export DEMO_COLOUR=green` gave `green`; after `unset DEMO_COLOUR` it was `(not set)` again.

**What you proved.** (1) Activation changes *which* Python runs. (2) A variable set in a
terminal lives only in that terminal and the programs it starts. (3) The current folder is
where you *are*, not where the script *is*. These three facts explain mistakes 3, 6 and many
"it works on my machine" puzzles.
</details>

---

### Exercise 2 — Read three real error messages ●○○○○

For each error, write down: (a) the error type, (b) the file and line to look at, (c) your
best guess at the fix. Don't run anything. Just read.

**Error A**

```text
node:internal/modules/package_json_reader:301
  throw new ERR_MODULE_NOT_FOUND(packageName, fileURLToPath(base), null);
        ^

Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'dotenv' imported from
C:\Users\you\projects\breakjs\env-check.js
    at Object.getPackageJSONURL (node:internal/modules/package_json_reader:301:9)
    at packageResolve (node:internal/modules/esm/resolve:764:81)
    … (eight more node:internal lines)
  code: 'ERR_MODULE_NOT_FOUND'
}
```

**Error B**

```text
C:\Users\you\projects\breakpy\.venv\Scripts\python.exe: can't open file
'C:\\Users\\you\\projects\\breakpy\\env_chek.py': [Errno 2] No such file or directory
```

**Error C**

```text
Traceback (most recent call last):
  File "C:\Users\you\projects\breakpy\env_check.py", line 6, in <module>
    from dotenv import load_dotenv
ModuleNotFoundError: No module named 'dotenv'
```

<details>
<summary>✅ Solution</summary>

| | (a) Type | (b) Where to look | (c) Fix |
|---|---|---|---|
| A | `ERR_MODULE_NOT_FOUND` | not a line: the package is missing for `env-check.js` | run `npm install dotenv` (or `npm install`) **in that folder** |
| B | file not found (`Errno 2`) | the file name itself: `env_chek.py` | a typo: run `python env_check.py`. Press Tab to finish names |
| C | `ModuleNotFoundError` | `env_check.py`, line 6 | activate the venv, then `pip install python-dotenv` (or `-r requirements.txt`) |

**Why these three.** Error A is the trap from §3.7: the top lines show Node's *own* file
(`package_json_reader:301`), not yours. The useful words are in the `Error` line. All the
`node:internal` lines can be skipped. Error B has no stack trace at all, because the program
never started. Error C is short, and the last line tells you everything. All three were real
outputs from Exercise 3.
</details>

---

### Exercise 3 — Break it seven ways ●●○○○

Start from your working `env-check` project. Make **one** change at a time. **Predict** what
happens, then run it, then undo the change.

1. JS: delete the `node_modules` folder, then run `node env-check.js`.
2. JS: change `"type": "module"` back to `"type": "commonjs"`.
3. JS: in a `"type": "module"` project, write `const dotenv = require("dotenv");`.
4. Python: run `env_check.py` with a Python that does not have `python-dotenv`.
5. Either: delete the `import "dotenv/config"` / `load_dotenv()` line.
6. Either: run the file with a one-letter typo in its name.
7. Either: type the command name wrong (`nod`, `pyhton`).

<details>
<summary>✅ Solution</summary>

| # | What you see (verified) | Why |
|---|---|---|
| 1 | `Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'dotenv' imported from …\env-check.js` | `package.json` lists `dotenv`, but nobody downloaded it. `npm install` rebuilds `node_modules`. |
| 2 | `SyntaxError: Cannot use import statement outside a module`, plus a warning to set `"type": "module"` | `"commonjs"` files must use `require`. |
| 3 | `ReferenceError: require is not defined in ES module scope, you can use import instead` | ES modules have no `require`. |
| 4 | `ModuleNotFoundError: No module named 'dotenv'` | this Python has no such package. We reproduced it with a fresh, empty venv. |
| 5 | **No error.** `❌ GROQ_API_KEY is not set`, even though `.env` is full | nothing read the file. The silent failure: the most confusing one. |
| 6 | JS: `Error: Cannot find module 'C:\…\env-chek.js'` (code `MODULE_NOT_FOUND`) · PY: `can't open file '…env_chek.py': [Errno 2] No such file or directory` | the file does not exist at that path. |
| 7 | PowerShell: `nod: The term 'nod' is not recognized as a name of a cmdlet, function, script file, or executable program.` · bash: `/usr/bin/bash: line 1: nod: command not found` (exit code 127) | no folder in `PATH` has a program with that name (§6.1). |

Exit codes we measured: Node errors exited with `1`. Python's "can't open file" exited with `2`.
A missing command in bash exited with `127`.

Repro files for #3 and #5:

```js
// req.js — #3: require inside a "type": "module" project
const dotenv = require("dotenv");
dotenv.config();
```

```python
# env_check_no_load.py — #5: forgot to load .env
import os

# from dotenv import load_dotenv     ← removed
# load_dotenv()                      ← removed

value = os.environ.get("GROQ_API_KEY")
print("set" if value else "not set")   # prints: not set
```

**The lesson.** Six of the seven break loudly, with a clear message. Number 5 breaks silently.
That is why `env-check` exists: it turns a silent problem into a clear ❌ line.
</details>

---

### Exercise 4 — Check every variable in `.env.example` ●●●○○

Right now the variable names are written inside `env-check`. If you add a variable to
`.env.example`, you must remember to add it to the script too. Write `check-example` in both
languages. It reads `.env.example`, collects every variable **name**, and reports which ones are
set. It exits with code 1 if any are missing.

Rules: skip empty lines and lines starting with `#`. The name is everything before the first
`=`. It must also work when the file has Windows line endings.

<details>
<summary>✅ Solution</summary>

```js
// check-example.js — is every variable named in .env.example set?
import "dotenv/config";
import { readFileSync } from "node:fs";

const names = readFileSync(".env.example", "utf8")
  .split("\n")
  .map((line) => line.trim())                       // also removes Windows "\r"
  .filter((line) => line !== "" && !line.startsWith("#"))
  .map((line) => line.split("=")[0].trim());

const missing = names.filter((name) => !process.env[name]);

for (const name of names) {
  console.log(`  ${name.padEnd(15)} ${process.env[name] ? "✅ set" : "❌ missing"}`);
}
if (missing.length > 0) {
  console.log(`\n${missing.length} missing: ${missing.join(", ")}`);
  process.exit(1);
}
console.log("\nEvery variable in .env.example is set.");
```

```python
# check_example.py — is every variable named in .env.example set?
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

names = []
for line in Path(".env.example").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#"):
        names.append(line.split("=")[0].strip())

missing = [name for name in names if not os.environ.get(name)]

for name in names:
    print(f"  {name:<15} {'✅ set' if os.environ.get(name) else '❌ missing'}")
if missing:
    print(f"\n{len(missing)} missing: {', '.join(missing)}")
    sys.exit(1)
print("\nEvery variable in .env.example is set.")
```

With the `.env.example` from §3.6, and both files saved with Windows line endings, both scripts
printed the same thing:

```text
$ copy .env.example to .env, leave it empty
  GROQ_API_KEY    ❌ missing
  GOOGLE_API_KEY  ❌ missing

2 missing: GROQ_API_KEY, GOOGLE_API_KEY          (exit code 1)

$ fill in GROQ_API_KEY only
  GROQ_API_KEY    ✅ set
  GOOGLE_API_KEY  ❌ missing

1 missing: GOOGLE_API_KEY                        (exit code 1)
```

**Why this design.** `.env.example` becomes the single list of what the project needs. Add a
line there, and the check knows about it. That stops a common team problem: "it works for me"
because one person has a variable the others never heard about. `trim()` / `strip()` removes the
invisible `\r` that Windows adds at the end of each line.
</details>

---

### Exercise 5 — 🎯 StudyBuddy v0: an empty, correctly set up project ●●●○○

StudyBuddy is the study assistant you build across this course. Today it gets a home. Create a
folder named `studybuddy` that:

1. is a git repository with a `.gitignore` that hides secrets, `node_modules/` and `.venv/`;
2. is a JavaScript project with `"type": "module"` and `dotenv` installed;
3. is a Python project with a `.venv` and a `requirements.txt` containing `python-dotenv`;
4. has `.env.example` (committed) and `.env` (not committed);
5. contains `env-check.js` and `env_check.py` from §4.6 and §5.6;
6. has a front door, `studybuddy.js` and `studybuddy.py`, that refuses to start without
   `GROQ_API_KEY` and prints a helpful message;
7. has one commit, and `.env` is **not** in it.

<details>
<summary>✅ Solution</summary>

**The commands** (PowerShell shown; bash differences in comments):

```powershell
mkdir studybuddy
cd studybuddy
git init

# JavaScript side
npm init -y
npm pkg set type=module
npm install dotenv

# Python side
python -m venv .venv                       # macOS/Linux: python3 -m venv .venv
.venv\Scripts\Activate.ps1                 # macOS/Linux: source .venv/bin/activate
pip install python-dotenv
pip freeze > requirements.txt

# Secrets: example first, then your private copy
#   (create .gitignore and .env.example in VS Code, contents below)
cp .env.example .env                       # then edit .env and add your key
```

**`.gitignore`**

```gitignore
# Secrets — never commit these
.env
.env.local

# JavaScript: installed packages (rebuild with `npm install`)
node_modules/

# Python: virtual environment and cache files
.venv/
__pycache__/
*.pyc

# Editor and system clutter
.vscode/
.DS_Store
Thumbs.db
```

**`.env.example`**

```bash
# Copy this file to .env and fill in your own values.
# .env.example is committed to git. .env is NOT.
# Get the keys by following SETUP.md.

GROQ_API_KEY=
GOOGLE_API_KEY=
```

**The front door, in both languages:**

```js
// studybuddy.js — StudyBuddy v0: the front door. Day 1 starts filling it in.
import "dotenv/config";

if (!process.env.GROQ_API_KEY) {
  console.error("StudyBuddy needs GROQ_API_KEY.");
  console.error("Copy .env.example to .env and fill it in (see SETUP.md).");
  process.exit(1);
}
console.log("StudyBuddy v0 is set up. Nothing to do yet. See you on Day 1!");
```

```python
# studybuddy.py — StudyBuddy v0: the front door. Day 1 starts filling it in.
import os
import sys

from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("GROQ_API_KEY"):
    print("StudyBuddy needs GROQ_API_KEY.", file=sys.stderr)
    print("Copy .env.example to .env and fill it in (see SETUP.md).", file=sys.stderr)
    sys.exit(1)
print("StudyBuddy v0 is set up. Nothing to do yet. See you on Day 1!")
```

**Check before you commit:**

```bash
git status --short --untracked-files=all
git check-ignore -v .env node_modules .venv
```

```text
?? .env.example
?? .gitignore
?? env-check.js
?? env_check.py
?? package-lock.json
?? package.json
?? requirements.txt
?? studybuddy.js
?? studybuddy.py
.gitignore:2:.env	.env
.gitignore:6:node_modules/	node_modules
.gitignore:9:.venv/	.venv
```

No `.env`, no `node_modules`, no `.venv` in the list. Now commit:

```bash
git add .
git commit -m "StudyBuddy v0: empty JS + Python project"
git ls-files
```

```text
.env.example
.gitignore
env-check.js
env_check.py
package-lock.json
package.json
requirements.txt
studybuddy.js
studybuddy.py
```

**Run it:**

```text
$ node studybuddy.js            (with GROQ_API_KEY in .env)
StudyBuddy v0 is set up. Nothing to do yet. See you on Day 1!

$ python studybuddy.py          (with .env renamed for a moment)
StudyBuddy needs GROQ_API_KEY.
Copy .env.example to .env and fill it in (see SETUP.md).          (exit code 1)
```

**The real test: a fresh copy.** We cloned the repository into a new folder and rebuilt it:
`npm install` (`found 0 vulnerabilities`), a new venv, `pip install -r requirements.txt`, and
`cp .env.example .env`. `env_check.py` then reported exactly one problem: `GROQ_API_KEY ❌
missing`. That is correct, because secrets never travel with the code. Everything else came
back from two small lists.

**Why this design.** Everything that can be rebuilt (`node_modules`, `.venv`) stays out of git.
Everything needed to rebuild it (`package.json`, `package-lock.json`, `requirements.txt`) goes
in. Secrets stay out, but their *names* go in, through `.env.example`. And the front door fails
fast with a message a beginner can act on. A missing key is a two-second fix at start-up, but a
confusing error deep inside a library later.
</details>

---

## 9. Interview questions

### Basic

**Q1. What is an environment variable, and why are API keys stored in one?**

A named text value that a program receives from its environment when it starts, like
`GROQ_API_KEY`. Keys go there so they live outside the code. Code gets shared, committed and
screenshotted; the environment stays on the machine. The same code can then run with different
keys on a laptop, a test server and production.

---

**Q2. What is the difference between `.env` and `.env.example`?**

`.env` holds the real values and is listed in `.gitignore`, so it is never committed.
`.env.example` holds the same variable *names* with empty or fake values, and is committed. It
documents what the project needs. A new teammate copies it to `.env` and fills in their own
values.

---

**Q3. What problem does a Python virtual environment solve?**

Without one, every project shares one set of installed packages. Two projects needing different
versions of the same package break each other. A venv is a per-project folder with its own
Python and its own packages. It is rebuilt from `requirements.txt` and never committed.

---

**Q4. What do `git add` and `git commit` each do?**

`git add` puts changes into the staging area: "these go into the next snapshot". `git commit`
saves the staged changes as a permanent snapshot in history, with a message. Two steps let you
choose exactly what goes into each snapshot.

---

**Q5. What is the difference between an absolute and a relative path?**

An absolute path starts from the top of the disk (`C:\…` or `/…`) and means the same file from
anywhere. A relative path starts from the current folder, so its meaning changes when you `cd`.
Many "file not found" errors are a relative path run from the wrong folder.

---

### Intermediate

**Q6. You added `.env` to `.gitignore`, but `git status` still shows it as modified. Why?**

`.gitignore` only affects files git does not track yet. This `.env` was committed earlier, so
git keeps tracking it. Run `git rm --cached .env` and commit. Then assume the key leaked: it is
still in history. Delete it on the provider's site and create a new one.

---

**Q7. How do you read a Node.js stack trace compared with a Python traceback?**

In Node.js, the error type and message are near the top, and the call list runs newest first.
In Python, the error type is the last line, and the list runs newest last. In both, skip the
runtime's own frames (`node:internal`, `site-packages`), find the first frame in your own file,
and read the code on that line. Remember that the bug is often in the caller, one step earlier.

---

**Q8. What does `"type": "module"` in `package.json` change?**

It makes Node.js treat `.js` files as ES modules: `import`/`export` work and `require` does
not. Without it, `.js` files are CommonJS. Then `import` fails with
`SyntaxError: Cannot use import statement outside a module`. npm 11's `npm init -y` writes
`"type": "commonjs"`, so you have to change it.

---

**Q9. A project runs on your laptop but fails on a teammate's with `ModuleNotFoundError`. What
do you check?**

That the package is listed in `requirements.txt` (or `package.json`). It is easy to install
something by hand and forget to record it. Then check that they installed inside an active
venv, from the right folder. Running the venv's Python by path removes the doubt.

---

### Advanced

**Q10. You pushed an API key to a public GitHub repository ten minutes ago. What do you do, in
order?**

First, revoke the key on the provider's website and create a new one, because public code is
scanned for keys. Second, check the provider's usage page for calls you didn't make. Third,
remove the file from tracking and add it to `.gitignore`. Rewriting history is optional
clean-up, not the fix: the old key is already dead. Finally, add a check, like a `.gitignore`
review or a secret-scanning hook, so it can't happen again.

---

**Q11. A variable is set both in the shell and in `.env`. Which value does the program see, and
why is that a good default?**

The shell's value. Both `dotenv` and `python-dotenv` do not overwrite variables that already
exist; we verified both. This lets production set real values through the environment, while
`.env` only fills gaps on a developer's laptop. Both libraries have an override option if you
really need the opposite: `override: true` / `override=True` made the `.env` value win in our test.

---

**Q12. How does the terminal decide which `python` runs when you type `python`?**

It walks the folders in the `PATH` variable in order and runs the first `python` it finds.
`where.exe python` or `which python` shows the candidates. Activating a venv puts the venv's
folder first in `PATH`; `deactivate` restores it. Calling `.venv/Scripts/python` (or
`.venv/bin/python`) by its path skips the search completely, which is why scripts and CI often
do that.

---

## 10. Recap

### What you learned

- ✅ The **terminal** runs one command at a time, from one **current folder**
- ✅ **Relative paths** start from the current folder; `.` is here, `..` is one up, `~` is home
- ✅ **Node.js** runs `.js` files and **Python** runs `.py` files; the course needs Node 20+ and Python 3.10+
- ✅ npm 11 writes `"type": "commonjs"`. **Change it to `"module"`** before using `import`
- ✅ Python packages go into a **venv**: create, activate, then install. `requirements.txt` rebuilds it
- ✅ **git**: `init`, `status`, `add`, `commit`. Write **`.gitignore` before the first `add`**
- ✅ A committed key stays in **history**. Replace it; don't just delete the file
- ✅ Secrets live in **`.env`**; their names live in **`.env.example`**; code reads them with dotenv
- ✅ JS dotenv looks in the **current folder**; Python's starts at the **script's folder**. The shell's value wins
- ✅ Read errors in order: **type and message → your file and line → the code there**. Node: top. Python: bottom
- ✅ The crash line is not always the wrong line. Check what the **caller** passed in
- ✅ Ask for help with **what you ran, what you expected, what happened, versions**, and never the key

### The toolkit at a glance

```
   new project:   mkdir → cd → git init → .gitignore → npm init -y + npm pkg set type=module
                  → python -m venv .venv + activate → install → .env.example → .env → commit
   every session: cd into the project → activate .venv → node env-check.js / python env_check.py
   on an error:   read the type → find YOUR file:line → read that line and the caller → search the message
```

### Tomorrow

**[Day 0B — Programming for AI](day-00b-programming-for-ai.md)**: today your scripts only read
local settings. Every AI app also talks to a model over the internet, and waits for the answer.
Tomorrow you learn the four ideas behind that, in both languages:

- **JSON**: the format the data travels in;
- **HTTP** requests: how a program asks another computer for something;
- **async/await**: waiting for an answer without freezing;
- **schemas** with Zod and Pydantic: checking that the answer has the shape you expect.

### Quick self-check

1. You run `python env_check.py` and get `ModuleNotFoundError: No module named 'dotenv'`, but
   you are sure you installed it yesterday. What are the two most likely causes?
2. Your `.env` file is correct, but `node env-check.js` prints `❌ GROQ_API_KEY is not set`.
   Name three possible reasons.
3. In a Python traceback, where do you look first, and where in a Node.js stack trace?

<details>
<summary>Answers</summary>

1. The venv is not active in this new terminal, so a different Python runs. Or you installed
   it into a different Python, such as the main one, without the venv on. Check with
   `python -c "import sys; print(sys.executable)"`; the path should contain `.venv`.

2. Any of these. The `import "dotenv/config"` line is missing. You ran the script from another
   folder, and JS dotenv only looks in the current folder. Or Windows PowerShell 5.1 saved the
   `.env` file as UTF-16, so dotenv found nothing. Also check that the file is named exactly
   `.env`, not `.env.txt`.

3. Python: the **last line** (error type and message), then upwards to the first frame in your
   own file. Node.js: the line near the **top** that starts with `…Error:`, then the first
   `at …` line that points at your file. Skip `node:internal` and `site-packages` frames.
</details>

---

<div align="center">

**[← Course home](../README.md)** · **[Week 0 index](README.md)** · **[Day 0B — Programming for AI →](day-00b-programming-for-ai.md)**

</div>
