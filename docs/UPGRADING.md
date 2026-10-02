# Upgrading

What a release has to tell a household that no commit subject had room for: a
figure that will read differently afterwards, a setting worth checking, a
reading that is correct and looks like a fault.

The release notes are otherwise built from the commit subjects, which is right -
they cannot then disagree with the version about what shipped - but a subject
says what was changed rather than what somebody will see.

## How this file is used

Write the paragraph under a heading spelled exactly `## Unreleased`, in the same
commit as the change it describes. The release prints it under **Upgrading** in
the GitHub release body, which is what Home Assistant shows in the update
notification, and then replaces the heading with the version it cut. So the
sections below are an archive, not a list to tidy up.

The heading carries no version while it waits, deliberately. The version comes
from the commits at release time, and a paragraph filed under a number somebody
predicted is one that disappears the day the prediction is wrong.

Most releases need nothing here. A paragraph a household did not need teaches
them that this section is not worth reading, which is the one thing it cannot
survive.

Releases before 0.7.0 carry their notes on the
[releases page](https://github.com/consultingtedds/ha-home-energy-advisor/releases)
only; this file began with the mechanism that writes it.
