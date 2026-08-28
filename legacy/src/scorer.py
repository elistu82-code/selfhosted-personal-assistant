import re
from typing import Dict, Any, List

from similarity import find_similar_memories, classify_similarity


RISK_TERMS = {
    "security": [
        "ssh", "firewall", "ufw", "fail2ban", "crowdsec", "auth",
        "authentication", "authorization", "password", "passwort",
        "token", "api key", "secret", "ssl", "tls", "https",
        "reverse proxy", "vpn", "tailscale", "expose", "port öffnen"
    ],
    "cost": [
        "kosten", "cost", "billing", "rechnung", "api kosten",
        "subscription", "abo", "bezahlen", "payment", "stripe"
    ],
    "architecture": [
        "architektur", "architecture", "datenbank schema", "schema",
        "migration", "refactor", "breaking change", "infrastruktur",
        "docker compose", "compose", "netzwerk", "volume", "volumes"
    ],
    "global_rule": [
        "global rule", "globalrules", "immer", "nie", "ab jetzt",
        "grundsätzlich", "dauerhaft", "regel", "rule"
    ],
    "arr_stack": [
        "arr stack", "arr-stack", "sabnzbd", "radarr", "sonarr",
        "prowlarr", "jellyseerr", "jellyfin", "usenet", "indexer",
        "tracker", "download client"
    ],
}


DISCARD_TERMS = [
    "einmalig", "nur diesmal", "kurzfristig", "temporär",
    "egal", "nicht speichern", "irrelevant"
]


FUTURE_TERMS = [
    "später", "irgendwann", "langfristig", "zukunft",
    "future", "noch nicht", "aktuell nicht", "erstmal nicht"
]


GLOBAL_RULE_TERMS = [
    "immer", "nie", "niemals", "ab jetzt", "grundsätzlich",
    "global rule", "globalrules", "regel für alles"
]


PROJECT_TERMS = [
    "repo", "repository", "github", "codex", "agents.md",
    "src/", "docs/", "bug", "feature", "refactor", "commit",
    "branch", "pull request", "projekt"
]


LESSON_TERMS = [
    "lösung", "problem", "ursache", "lesson", "gelernt",
    "wiederverwendbar", "fix", "bugfix", "troubleshooting",
    "fehler", "workaround"
]


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9äöüß\s/_.]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_any(text: str, terms: List[str]) -> bool:
    n = normalize(text)
    return any(normalize(term) in n for term in terms)


def detect_risk_flags(text: str) -> List[str]:
    flags = []

    for flag, terms in RISK_TERMS.items():
        if contains_any(text, terms):
            flags.append(flag)

    return sorted(set(flags))


def infer_status(text: str) -> str:
    n = normalize(text)

    if contains_any(n, FUTURE_TERMS):
        return "future"

    return "active"


def infer_score(text: str, provided_score: Any = None) -> int:
    """
    Score 1 = verwerfen
    Score 2 = projektbezogen
    Score 3 = wiederverwendbare Lesson
    Score 4 = global nützlich
    Score 5 = dauerhafte Regel, nur Review
    """
    if provided_score is not None:
        try:
            score = int(provided_score)
            if 1 <= score <= 5:
                return score
        except Exception:
            pass

    n = normalize(text)

    if contains_any(n, DISCARD_TERMS):
        return 1

    if contains_any(n, GLOBAL_RULE_TERMS):
        return 5

    risks = detect_risk_flags(n)

    if "global_rule" in risks:
        return 5

    if "security" in risks or "architecture" in risks or "cost" in risks:
        return 4

    if contains_any(n, PROJECT_TERMS):
        return 2

    if contains_any(n, LESSON_TERMS):
        return 3

    # Default: lieber nicht zu hoch bewerten.
    return 2


def infer_target(score: int, topic_hint: str = "", text: str = "") -> str:
    """
    Zielvorschlag. Der Writer entscheidet später final.
    """
    combined = normalize(f"{topic_hint} {text}")

    if score <= 1:
        return "DISCARD"

    if score == 5:
        return "90_Inbox/ReviewQueue.md"

    if "linux" in combined or "fedora" in combined or "hyprland" in combined:
        return "10_Linux/LessonsLearned.md"

    if "homelab" in combined or "docker" in combined or "tailscale" in combined or "arr" in combined:
        return "20_Homelab/LessonsLearned.md"

    if "studium" in combined or "uni" in combined or "klausur" in combined:
        return "30_Studium/LessonsLearned.md"

    if "fitness" in combined or "training" in combined or "ernährung" in combined:
        return "40_Fitness/Training.md"

    if "finanzen" in combined or "youtube" in combined or "business" in combined:
        return "50_Finanzen/LessonsLearned.md"

    if score == 4:
        return "00_Global/GlobalLessons.md"

    return "90_Inbox/ReviewQueue.md"


def requires_review(score: int, risk_flags: List[str], action: str = "") -> bool:
    """
    Harte Review-Regeln.
    """
    if score >= 5:
        return True

    if action.upper() in {"SUPERSEDE", "DELETE", "OVERWRITE"}:
        return True

    hard_flags = {
        "security",
        "cost",
        "architecture",
        "global_rule",
        "arr_stack",
    }

    if any(flag in hard_flags for flag in risk_flags):
        return True

    return False


def evaluate_memory_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bewertet einen Queue-Eintrag.
    """
    content = str(proposal.get("content", ""))
    topic_hint = str(proposal.get("topic_hint", ""))
    suggested_action = str(proposal.get("suggested_action", "ADD")).upper()

    combined_text = f"{topic_hint}\n{content}"

    score = infer_score(combined_text, proposal.get("suggested_score"))
    status = infer_status(combined_text)
    risk_flags = detect_risk_flags(combined_text)

    similar = find_similar_memories(content, topic_hint, limit=5)
    similarity_info = classify_similarity(similar)

    if similarity_info.get("duplicate_risk") == "high":
        risk_flags.append("duplicate_high")
    elif similarity_info.get("duplicate_risk") == "medium":
        risk_flags.append("duplicate_medium")

    risk_flags = sorted(set(risk_flags))

    review = requires_review(score, risk_flags, suggested_action) or similarity_info.get("requires_review", False)
    target = infer_target(score, topic_hint, content)

    if "arr_stack" in risk_flags:
        final_action = "BLOCKED"
        target = "90_Inbox/ReviewQueue.md"
        review = True
    elif score <= 1:
        final_action = "DISCARD"
    elif review:
        final_action = "REVIEW"
        target = "90_Inbox/ReviewQueue.md"
    else:
        final_action = suggested_action if suggested_action in {"ADD", "MERGE"} else "ADD"

    top_match = similarity_info.get("top_match")

    return {
        "proposal_id": proposal.get("id", ""),
        "score": score,
        "status": status,
        "risk_flags": risk_flags,
        "requires_review": review,
        "suggested_action": suggested_action,
        "final_action": final_action,
        "target": target,
        "duplicate_risk": similarity_info.get("duplicate_risk"),
        "top_similarity": similarity_info.get("top_similarity"),
        "top_match_id": top_match.get("id") if top_match else None,
        "top_match_path": top_match.get("path") if top_match else None,
        "reason": build_reason(score, status, risk_flags, review, final_action, target),
    }


def build_reason(score: int, status: str, risk_flags: List[str], review: bool, action: str, target: str) -> str:
    parts = [
        f"score={score}",
        f"status={status}",
        f"action={action}",
        f"target={target}",
    ]

    if risk_flags:
        parts.append("risk_flags=" + ",".join(risk_flags))

    if review:
        parts.append("review_required=true")

    return "; ".join(parts)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Nutzung:")
        print("  python3 src/scorer.py path/to/proposal.json")
        sys.exit(1)

    path = sys.argv[1]

    with open(path, "r", encoding="utf-8") as f:
        proposal = json.load(f)

    result = evaluate_memory_proposal(proposal)
    print(json.dumps(result, indent=2, ensure_ascii=False))
