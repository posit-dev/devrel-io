#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p output

# $(velocirepo list-projects --ids-only);
for project in quarto positron plotnine; do
  echo "Rendering ${project}"
  uv run quarto render view.qmd -P "project:${project}" --output-dir "output/${project}/"
done
