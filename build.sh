#!/bin/bash
#
# Build script for Guerdon's personal website.
# Assembles component HTML files and JS into a single index.html.
#

set -e

OUTPUT="index.html"
COMPONENTS="components"
JS="js"

{
    # Head & body open
    cat "$COMPONENTS/head.html"
    echo ""

    # Navigation (includes canvas element)
    cat "$COMPONENTS/nav.html"
    echo ""

    # Modal overlay
    cat "$COMPONENTS/modal.html"
    echo ""

    # Page sections
    cat "$COMPONENTS/hero.html"
    echo ""
    cat "$COMPONENTS/about.html"
    echo ""
    cat "$COMPONENTS/roles.html"
    echo ""
    cat "$COMPONENTS/resume.html"
    echo ""
    cat "$COMPONENTS/society.html"
    echo ""
    cat "$COMPONENTS/projects.html"
    echo ""
    cat "$COMPONENTS/footer.html"
    echo ""

    # JavaScript
    echo "    <!-- Script for Paper Airplanes -->"
    echo "    <script>"
    cat "$JS/paper-planes.js"
    echo ""
    echo "    </script>"
    echo ""

    echo "    <!-- Content for Modals -->"
    echo "    <script>"
    cat "$JS/modal.js"
    echo ""
    echo "    </script>"

    # Close body & html
    echo "</body>"
    echo "</html>"
} > "$OUTPUT"

echo "Built $OUTPUT successfully."
