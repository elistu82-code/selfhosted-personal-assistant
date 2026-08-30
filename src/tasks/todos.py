import re
from difflib import SequenceMatcher

from src.config import VAULT_PATH
from src.memory.router import get_domain


START = "<!-- personal-assistant:todos:start -->"
END = "<!-- personal-assistant:todos:end -->"


def todo_file():
    domain = get_domain("todos")

    if not domain:
        raise RuntimeError("Todos-Domain fehlt")

    relative = domain.get("target_file")

    if not relative:
        raise RuntimeError("Todo target_file fehlt")

    path = (VAULT_PATH / relative).resolve()

    if VAULT_PATH not in path.parents:
        raise RuntimeError("Ungültiger Todo-Pfad")

    if not path.parent.exists():
        raise RuntimeError(
            f"Todo-Ordner fehlt: {path.parent}"
        )

    return path


def normalize(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.strip().casefold(),
    )


def _load():
    path = todo_file()

    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = "# Todos\n"

    if START in text and END in text:
        before, rest = text.split(START, 1)
        managed, after = rest.split(END, 1)
    else:
        before = text.rstrip() + "\n\n"
        managed = ""
        after = "\n"

    tasks = []

    pattern = re.compile(
        r"^- \[([ xX])\] "
        r"\[(LOW|NORMAL|HIGH|CRITICAL)\] "
        r"(?:\[([^\]]+)\] )?"
        r"(.+)$"
    )

    for line in managed.splitlines():
        match = pattern.match(line.strip())

        if not match:
            continue

        tasks.append({
            "done": match.group(1).lower() == "x",
            "priority": match.group(2).lower(),
            "scope": match.group(3),
            "content": match.group(4).strip(),
        })

    return before, after, tasks


def _save(before, after, tasks):
    lines = []

    for task in tasks:
        state = "x" if task["done"] else " "
        priority = task["priority"].upper()

        scope = (
            f'[{task["scope"]}] '
            if task["scope"]
            else ""
        )

        lines.append(
            f'- [{state}] [{priority}] '
            f'{scope}{task["content"]}'
        )

    managed = "\n".join(lines)

    text = (
        before
        + START
        + "\n"
        + managed
        + ("\n" if managed else "")
        + END
        + after
    )

    todo_file().write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )


def add_todo(
    content: str,
    scope: str | None = None,
    priority: str = "normal",
):
    before, after, tasks = _load()

    target = normalize(content)

    for task in tasks:
        if (
            not task["done"]
            and normalize(task["content"]) == target
            and task["scope"] == scope
        ):
            return False

    tasks.append({
        "done": False,
        "priority": priority,
        "scope": scope,
        "content": content.strip(),
    })

    _save(before, after, tasks)

    return True


def list_todos(scope: str | None = None):
    _, _, tasks = _load()

    return [
        task
        for task in tasks
        if not task["done"]
        and (
            scope is None
            or task["scope"] == scope
        )
    ]


def complete_todo(
    query: str,
    scope: str | None = None,
):
    before, after, tasks = _load()

    candidates = []

    for index, task in enumerate(tasks):
        if task["done"]:
            continue

        if scope and task["scope"] != scope:
            continue

        score = SequenceMatcher(
            None,
            normalize(query),
            normalize(task["content"]),
        ).ratio()

        candidates.append(
            (score, index)
        )

    if not candidates:
        return None

    score, index = max(candidates)

    if score < 0.45:
        return None

    tasks[index]["done"] = True
    completed = tasks[index]

    _save(before, after, tasks)

    return completed
