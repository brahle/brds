#!/bin/bash

# Get the list of tags and sort them in version order
LATEST_TAG=$(git tag -l | sort -V | tail -n1)

# Split the tag into major, minor, and patch versions
IFS='.' read -ra ADDR <<< "$LATEST_TAG"
MAJOR=${ADDR[0]}
MINOR=${ADDR[1]}
PATCH=${ADDR[2]}

# Decide which part to increment based on the passed argument
case "$1" in
  --major)
    MAJOR=$((MAJOR+1))
    MINOR=0
    PATCH=0
    ;;
  --minor)
    MINOR=$((MINOR+1))
    PATCH=0
    ;;
  --patch)
    PATCH=$((PATCH+1))
    ;;
  *)
    # By default increment minor version
    MINOR=$((MINOR+1))
    PATCH=0
    ;;
esac

# Print the next version
echo "$MAJOR.$MINOR.$PATCH"
