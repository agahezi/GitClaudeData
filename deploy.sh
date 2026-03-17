#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# deploy.sh — Deploy current directory contents to ~/.claude
#
# Flow:
#   1. Scan — what will be copied
#   2. Detect conflicts — files that already exist at target
#   3. If conflicts — ask what to do for each one
#   4. Final confirmation before executing
#
# Usage:
#   bash deploy.sh
#   bash deploy.sh --verbose
# ═══════════════════════════════════════════════════════════════
set -e

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.claude"
VERBOSE=false
THIS_SCRIPT="$(basename "${BASH_SOURCE[0]}")"

for arg in "$@"; do
  case $arg in
    --verbose) VERBOSE=true ;;
    --help)
      echo "Usage: bash deploy.sh [--verbose]"
      echo "  Default: preview then confirm before copying to ~/.claude"
      echo "  --verbose: show each file during copy"
      exit 0 ;;
  esac
done

# ─── UI ───────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
RED='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'
ok()       { echo -e "  ${GREEN}✓${RESET} $*"; }
warn()     { echo -e "  ${YELLOW}⚠${RESET} $*"; }
conflict() { echo -e "  ${RED}!${RESET} $*"; }
preview()  { echo -e "  ${CYAN}→${RESET} $*"; }
fail()     { echo -e "  ${RED}✗${RESET} $*"; exit 1; }

# ─── Should skip ──────────────────────────────────────────────
# Only .git and the script itself are excluded — everything else is copied.
should_skip() {
  local name="$1"
  [ "$name" = ".git" ]         && return 0
  [ "$name" = "$THIS_SCRIPT" ] && return 0
  return 1
}

# ─── Make executable if needed ────────────────────────────────
make_executable_if_needed() {
  local file="$1"
  case "$file" in
    *.sh|*.py) chmod +x "$file" ;;
  esac
}

# ─── Collect all files to copy (flat list: src|dst) ──────────
collect_files() {
  local base_src="$1"
  local base_dst="$2"

  # root-level files
  while IFS= read -r -d '' f; do
    fname="$(basename "$f")"
    should_skip "$fname" && continue
    echo "$f|$base_dst/$fname"
  done < <(find "$base_src" -maxdepth 1 -type f -print0 2>/dev/null)

  # recursive dirs
  while IFS= read -r -d '' dir; do
    dname="$(basename "$dir")"
    should_skip "$dname" && continue
    while IFS= read -r -d '' f; do
      rel="${f#$base_src/}"
      local skip=false
      local saved_IFS="$IFS"; IFS='/'
      local parts=($rel); IFS="$saved_IFS"
      for part in "${parts[@]}"; do
        should_skip "$part" && skip=true && break
      done
      $skip && continue
      echo "$f|$base_dst/$rel"
    done < <(find "$dir" -type f -print0 2>/dev/null)
  done < <(find "$base_src" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)
}

# ─── Validate ─────────────────────────────────────────────────
[ "$SOURCE_DIR" = "$TARGET_DIR" ] && fail "Source and target are the same directory."

# ─── Scan ─────────────────────────────────────────────────────
ALL_PAIRS=()
while IFS= read -r line; do
  ALL_PAIRS+=("$line")
done < <(collect_files "$SOURCE_DIR" "$TARGET_DIR")

if [ ${#ALL_PAIRS[@]} -eq 0 ]; then
  warn "No files found to copy."
  exit 0
fi

NEW_PAIRS=()
CONFLICT_PAIRS=()
for pair in "${ALL_PAIRS[@]}"; do
  dst="${pair#*|}"
  if [ -f "$dst" ]; then
    CONFLICT_PAIRS+=("$pair")
  else
    NEW_PAIRS+=("$pair")
  fi
done

# ─── Preview ──────────────────────────────────────────────────
clear
echo ""
echo -e "${BOLD}  deploy.sh — Claude Directory Sync${RESET}"
echo "  ══════════════════════════════════════════════════"
echo "  Source : $SOURCE_DIR"
echo "  Target : $TARGET_DIR"
echo "  ══════════════════════════════════════════════════"
echo ""

if [ ${#NEW_PAIRS[@]} -gt 0 ]; then
  echo -e "  ${BOLD}New files ${DIM}(${#NEW_PAIRS[@]}):${RESET}"
  for pair in "${NEW_PAIRS[@]}"; do
    dst="${pair#*|}"
    rel_dst="${dst#$TARGET_DIR/}"
    preview "$rel_dst"
  done
  echo ""
fi

if [ ${#CONFLICT_PAIRS[@]} -gt 0 ]; then
  echo -e "  ${RED}${BOLD}Conflicts — files that already exist at target ${DIM}(${#CONFLICT_PAIRS[@]}):${RESET}"
  for pair in "${CONFLICT_PAIRS[@]}"; do
    dst="${pair#*|}"
    rel_dst="${dst#$TARGET_DIR/}"
    conflict "$rel_dst"
  done
  echo ""
fi

echo "  ──────────────────────────────────────────────────"
echo -e "  Total: ${BOLD}$((${#NEW_PAIRS[@]} + ${#CONFLICT_PAIRS[@]})) files${RESET}"
echo -e "  New: ${GREEN}${#NEW_PAIRS[@]}${RESET}  |  Conflicts: ${RED}${#CONFLICT_PAIRS[@]}${RESET}"
echo ""

# ─── Resolve conflicts ────────────────────────────────────────
declare -A DECISIONS
APPLY_ALL_DECISION=""

if [ ${#CONFLICT_PAIRS[@]} -gt 0 ]; then
  echo -e "  ${BOLD}Resolve conflicts:${RESET}"
  echo ""
  echo -e "  ${DIM}Choose how to handle files that already exist at the target.${RESET}"
  echo -e "  ${DIM}You can set one decision for all, or decide file by file.${RESET}"
  echo ""
  echo -e "  ${BOLD}Apply to all conflicts:${RESET}"
  echo "  1) Overwrite all  — replace with new version"
  echo "  2) Skip all       — keep existing"
  echo "  3) Ask me per file"
  echo ""
  echo -ne "  Choice [1/2/3]: "
  read -r global_choice

  case "$global_choice" in
    1) APPLY_ALL_DECISION="overwrite" ;;
    2) APPLY_ALL_DECISION="skip" ;;
    *) APPLY_ALL_DECISION="" ;;
  esac

  echo ""

  for pair in "${CONFLICT_PAIRS[@]}"; do
    src="${pair%%|*}"
    dst="${pair#*|}"
    rel_dst="${dst#$TARGET_DIR/}"

    if [ -n "$APPLY_ALL_DECISION" ]; then
      DECISIONS["$src"]="$APPLY_ALL_DECISION"
      if [ "$APPLY_ALL_DECISION" = "overwrite" ]; then
        echo -e "  ${YELLOW}⚠${RESET} $rel_dst  ${DIM}→ will overwrite${RESET}"
      else
        echo -e "  ${DIM}–${RESET} $rel_dst  ${DIM}→ will skip${RESET}"
      fi
    else
      echo -e "  ${RED}!${RESET} ${BOLD}$rel_dst${RESET}"
      echo -e "    1) ${YELLOW}Overwrite${RESET}  — replace with new version"
      echo -e "    2) ${DIM}Skip${RESET}       — keep existing"
      echo -ne "    Choice [1/2]: "
      read -r file_choice
      case "$file_choice" in
        1) DECISIONS["$src"]="overwrite"
           echo -e "    ${YELLOW}→ will overwrite${RESET}" ;;
        *) DECISIONS["$src"]="skip"
           echo -e "    ${DIM}→ will skip${RESET}" ;;
      esac
      echo ""
    fi
  done

  echo ""
  echo "  ──────────────────────────────────────────────────"
  OW=0; SK=0
  for pair in "${CONFLICT_PAIRS[@]}"; do
    src="${pair%%|*}"
    [ "${DECISIONS[$src]}" = "overwrite" ] && OW=$((OW+1)) || SK=$((SK+1))
  done
  echo -e "  Conflicts: ${YELLOW}$OW will overwrite${RESET}  |  ${DIM}$SK will skip${RESET}"
  echo ""
fi

# ─── Final confirm ────────────────────────────────────────────
echo -e "  ${BOLD}Proceed with copy?${RESET} ${DIM}[y/N]${RESET} "
read -r answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
  echo ""
  echo "  Cancelled — no changes made."
  echo ""
  exit 0
fi

# ─── Execute ──────────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}Copying...${RESET}"
echo ""

COPIED=0; SKIPPED=0; OVERWRITTEN=0

for pair in "${ALL_PAIRS[@]}"; do
  src="${pair%%|*}"
  dst="${pair#*|}"
  rel_dst="${dst#$TARGET_DIR/}"

  if [ -f "$dst" ]; then
    decision="${DECISIONS[$src]:-skip}"
    if [ "$decision" = "overwrite" ]; then
      mkdir -p "$(dirname "$dst")"
      cp "$src" "$dst"
      make_executable_if_needed "$dst"
      warn "$rel_dst  ${DIM}(overwritten)${RESET}"
      OVERWRITTEN=$((OVERWRITTEN+1))
    else
      echo -e "  ${DIM}–${RESET} $rel_dst  ${DIM}(skipped)${RESET}"
      SKIPPED=$((SKIPPED+1))
    fi
  else
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    make_executable_if_needed "$dst"
    ok "$rel_dst"
    COPIED=$((COPIED+1))
  fi
done

# ─── Done ─────────────────────────────────────────────────────
echo ""
echo "  ──────────────────────────────────────────────────"
echo -e "  ${GREEN}${BOLD}✓ Deploy complete${RESET}"
echo ""
[ $COPIED -gt 0 ]      && echo -e "  ${GREEN}+${RESET} $COPIED new files copied"
[ $OVERWRITTEN -gt 0 ] && echo -e "  ${YELLOW}~${RESET} $OVERWRITTEN files overwritten"
[ $SKIPPED -gt 0 ]     && echo -e "  ${DIM}–${RESET} $SKIPPED files skipped"
echo "  Target: $TARGET_DIR"
echo "  Note: .sh and .py files were made executable automatically."
echo ""
