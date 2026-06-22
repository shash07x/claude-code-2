---
name: teamsync-deploy
description: Builds TeamSync and deploys it to the specified environment.
disable-model-invocation: true
argument-hint: [environment-name]
allowed-tools: Bash, Read
---

You are executing the TeamSync deploy command.
Target environment: $ARGUMENTS

Step 1: Run the build: `npm run build`
Step 2: Check the latest commit: !`git log -1 --oneline`
Step 3: Confirm the build succeeded, summarize what's being deployed, and list the next manual step for the user.
