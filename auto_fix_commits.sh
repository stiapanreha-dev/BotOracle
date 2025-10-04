#!/bin/bash
# Script to automatically remove Claude mentions from commit history

echo "🧹 Cleaning commit history from Claude mentions..."

# Use git filter-branch to rewrite commit messages
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --msg-filter 'sed -e ""/🤖 Generated with \[Claude Code\]/d"" -e ""/Co-Authored-By: Claude/d"" -e ""/^$/N;/^\n$/D""' -- --all

# Clean up refs
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ Done! History cleaned."
echo "📤 To push changes, run: git push --force --all"