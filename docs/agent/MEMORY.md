# Project Memory Policy

Статус: authoritative agent-facing guidance.

Этот документ задаёт repo-local policy для manual Hindsight workflow. Память дополняет checked-in docs, но не заменяет `AGENTS.md`, `docs/agent/TASK_ROUTING.md`, `docs/agent/VERIFY.md`, `docs/agent/RUNBOOK.md` и OpenSpec surfaces.

## Default Bank

- Default bank naming: `codex::<repo-name>`.
- Для этого репозитория normal-case bank: `codex::command-center-1c`.
- Если repo-local workflow когда-либо введёт отдельный bank override, он должен быть явно указан здесь или в root `AGENTS.md`.

Recommended shell vars:

```bash
export HINDSIGHT_URL=http://127.0.0.1:8889
export HINDSIGHT_BANK="codex::$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"
```

## Recall

Делай `recall` перед нетривиальной работой, когда нужно быстро восстановить устойчивые факты:

- новый или возвращающийся session по active change;
- рискованная docs/code/runtime задача, где важны conventions, previous fixes или gotchas;
- task, где уже был Beads/OpenSpec context, который дорого восстанавливать вручную.

Для routine lookup по фактам предпочитай `recall`. `reflect` используй только когда нужен synthesis или ответ на recurring higher-level question.

Manual recall example:

```bash
QUERY="project conventions, setup, pitfalls, previous fixes" uv run --directory /home/egor/code/hindsight/hindsight-clients/python python -c 'from hindsight_client import Hindsight; import json, os; c=Hindsight(base_url=os.environ.get("HINDSIGHT_URL", "http://127.0.0.1:8889")); r=c.recall(bank_id=os.environ["HINDSIGHT_BANK"], query=os.environ["QUERY"], budget="mid"); print(json.dumps([x.text for x in (r.results or [])], ensure_ascii=False, indent=2)); c.close()'
```

## Retain

Делай `retain` только после verified discovery, verified fix или другой проверенной находки, которая почти наверняка пригодится снова.

Нормальный retain-контент:

- что именно было проверено;
- что сработало или не сработало;
- устойчивое ограничение, gotcha или repo fact;
- active change state, который поможет безопасно продолжить работу позже.

Предпочитай компактную factual note и async retain с polling статуса.

Manual retain example:

```bash
CONTENT="Verified fix: ..." CONTEXT="verified-fix" uv run --directory /home/egor/code/hindsight/hindsight-clients/python python -c 'from hindsight_client import Hindsight; import json, os; c=Hindsight(base_url=os.environ.get("HINDSIGHT_URL", "http://127.0.0.1:8889")); r=c.retain_batch(bank_id=os.environ["HINDSIGHT_BANK"], items=[{"content": os.environ["CONTENT"], "context": os.environ.get("CONTEXT")}], retain_async=True); print(json.dumps({"operation_id": r.operation_id, "operation_ids": r.operation_ids}, ensure_ascii=False)); c.close()'
```

Poll async retain status:

```bash
OPERATION_ID="<paste-operation-id>" BANK_URI="$(python - <<'PY'
import os, urllib.parse
print(urllib.parse.quote(os.environ["HINDSIGHT_BANK"], safe=""))
PY
)" ; curl -sS "$HINDSIGHT_URL/v1/default/banks/$BANK_URI/operations/$OPERATION_ID"
```

Treat `status=completed` как success для retain itself.

## Allowed Note Types

Default high-signal note taxonomy ограничена следующими типами:

- `repo-fact` — устойчивый факт о структуре, tooling или workflow.
- `gotcha` — повторяемая ловушка, ограничение или важный edge case.
- `verified-fix` — проверенное исправление с указанием, что именно подтвердило успех.
- `active-change-note` — компактный state note по активному change, который нужен для безопасного resume.

## Do Not Retain By Default

`session-noise` запрещён как normal-case retain path. Не сохраняй по умолчанию:

- промежуточные статусы плана и “что делаю сейчас”;
- пересказ текущего user request;
- временный operational noise, который не переживёт текущую сессию;
- сырые логи и дампы без отдельной долгоживущей ценности;
- факты, уже полно и явно зафиксированные в authoritative docs без дополнительной ценности.

Negative examples:

- `Started step 2 of refactor-agent-guidance-governance.`
- `User asked me to look at docs.`
- `Console dumped 200 lines of npm output.`
- `INDEX.md exists.` when это уже без добавочной ценности зафиксировано в checked-in guidance.

## Reflect

Используй `reflect` sparingly, когда нужен synthesis-level ответ, а не простой lookup:

- safest way to approach recurring class of tasks;
- consolidated summary of durable repo conventions;
- high-level explanation of known risks before a larger change.

Manual reflect example:

```bash
QUERY="What is the safest way to approach this task in this repo?" uv run --directory /home/egor/code/hindsight/hindsight-clients/python python -c 'from hindsight_client import Hindsight; import os; c=Hindsight(base_url=os.environ.get("HINDSIGHT_URL", "http://127.0.0.1:8889")); r=c.reflect(bank_id=os.environ["HINDSIGHT_BANK"], query=os.environ["QUERY"], budget="low"); print(r.text); c.close()'
```

## Relationship To Checked-In Docs

- Checked-in docs остаются source of truth для repo-wide invariants, routes, validation и runtime behavior.
- Project memory хранит только то, что полезно переиспользовать между сессиями и ещё не оформлено лучше в checked-in surface.
- Если discovered fact уже должен жить в `AGENTS.md`, `docs/agent/*` или OpenSpec, сначала подумай о checked-in update, а не о memory dump.
