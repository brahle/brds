#!/bin/bash

# Display warning
echo "WARNING: This operation will create a version tag and push to GitHub"

# Get the next version
TAG=$(./next_version.sh "$@")

# Display the version
echo "Releasing version '${TAG}'"

# Write the version to a file
echo "${TAG}" > brds/VERSION

# Generate changelog and commit the changes (assuming ENV_PREFIX is set in your environment)
${ENV_PREFIX}gitchangelog > HISTORY.md

# Add files and commit
git add brds/VERSION HISTORY.md
git commit -m "release: version ${TAG} 🚀"

# Create git tag and push
echo "creating git tag : ${TAG}"
git tag ${TAG}
git push -u origin HEAD --tags

# Notification
echo "Github Actions will detect the new tag and release the new version."
