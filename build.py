#!/usr/bin/env python3
"""
Build script for Guerdon's personal website.
Parses content.md and assembles index.html from HTML templates.
"""

import re
import html


def parse_content(filepath):
    """Parse content.md into structured sections."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # Split into major sections by horizontal rules
    raw_sections = re.split(r'\n---\n', text)
    sections = {}

    for raw in raw_sections:
        raw = raw.strip()
        if not raw:
            continue

        # Get section name from first H1
        m = re.match(r'^# (.+)', raw)
        if not m:
            continue
        section_name = m.group(1).strip()
        body = raw[m.end():].strip()
        sections[section_name] = body

    return sections


def parse_metadata_lines(text):
    """Parse lines like '- key: value' into a dict, return (metadata, remaining_text)."""
    meta = {}
    lines = text.split('\n')
    consumed = 0
    for line in lines:
        m = re.match(r'^- (\w[\w\s]*?):\s*(.+)$', line)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
            consumed += 1
        elif line.strip() == '':
            consumed += 1
        else:
            break
    remaining = '\n'.join(lines[consumed:]).strip()
    return meta, remaining


def parse_list_items(text):
    """Parse markdown list items, return list of strings."""
    items = []
    for line in text.strip().split('\n'):
        m = re.match(r'^- (.+)$', line)
        if m:
            items.append(m.group(1).strip())
    return items


def get_subsection(body, heading, level=2):
    """Extract content under a heading of given level, stopping at next heading of same or higher level."""
    prefix = '#' * level
    # Match the heading, then capture until next heading of same or higher level (1..level #'s)
    # Build alternation for headings of level 1 through current level
    stop_patterns = '|'.join(rf'^{"#" * i} ' for i in range(1, level + 1))
    pattern = rf'^{prefix} {re.escape(heading)}\s*\n(.*?)(?={stop_patterns}|\Z)'
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''


def get_all_subsections(body, level=2):
    """Get all subsections at a given heading level as (name, content) pairs."""
    prefix = '#' * level
    # Split by headings at this level
    pattern = rf'^{prefix} (.+)$'
    parts = re.split(pattern, body, flags=re.MULTILINE)
    # parts[0] is text before first heading, then alternating name/content
    result = []
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ''
        result.append((name, content))
    return result


def get_all_subsections_at(body, level=3):
    """Get all subsections at a given heading level."""
    prefix = '#' * level
    pattern = rf'^{prefix} (.+)$'
    parts = re.split(pattern, body, flags=re.MULTILINE)
    result = []
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ''
        result.append((name, content))
    return result


def get_simple_value(body, heading, level=2):
    """Get the text content under a simple heading, stopping at any heading."""
    prefix = '#' * level
    # Match the heading, capture until next heading of ANY level
    pattern = rf'^{prefix} {re.escape(heading)}\s*\n(.*?)(?=^#+\s|\Z)'
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''


def escape(text):
    """Escape HTML entities in text."""
    return html.escape(text)


# ─── Section Builders ─────────────────────────────────────────────────────────


def build_head():
    with open('components/head.html', 'r', encoding='utf-8') as f:
        return f.read()


def build_nav():
    with open('components/nav.html', 'r', encoding='utf-8') as f:
        return f.read()


def build_modal():
    with open('components/modal.html', 'r', encoding='utf-8') as f:
        return f.read()


def build_hero(data):
    body = data['Hero']
    title = get_simple_value(body, 'Title')
    description = get_simple_value(body, 'Description')
    tags_raw = get_simple_value(body, 'Tags')
    tags = parse_list_items(tags_raw)

    tags_html = '\n'.join(
        f'                    <span class="px-3 py-1 border border-stone-300 rounded-sm">{t}</span>'
        for t in tags
    )

    return f"""    <!-- Hero Section -->
    <section class="min-h-[80vh] flex flex-col justify-center max-w-5xl mx-auto px-6 pt-24 relative z-10">
        <div class="max-w-3xl space-y-8">
            <h1 class="font-serif text-5xl md:text-6xl leading-tight font-medium text-stone-900">
                {title}
            </h1>

            <div class="space-y-6">
                <p class="font-sans text-lg text-stone-600 max-w-2xl leading-relaxed">
                    {description}
                </p>

                <div class="flex flex-wrap gap-3 font-mono text-xs uppercase tracking-wide text-stone-500 pt-4">
{tags_html}
                </div>
            </div>
        </div>
    </section>"""


def build_about(data):
    body = data['About']
    label = get_simple_value(body, 'Label')
    quote = get_simple_value(body, 'Quote')
    content_raw = get_simple_value(body, 'Content')
    focus_raw = get_simple_value(body, 'Current Focus')

    # Split content into paragraphs
    paragraphs = [p.strip() for p in content_raw.split('\n\n') if p.strip()]
    paragraphs_html = '\n'.join(
        f'                    <p class="leading-relaxed">\n                        {p}\n                    </p>'
        for p in paragraphs
    )

    # Parse focus items
    focus_items = []
    for line in focus_raw.split('\n'):
        m = re.match(r'^- (.+?):\s*(.+)$', line)
        if m:
            focus_items.append((m.group(1).strip(), m.group(2).strip()))

    # Build focus list - last item has no border, special styling for "Status"
    focus_lines = []
    for i, (key, value) in enumerate(focus_items):
        is_last = (i == len(focus_items) - 1)
        if is_last:
            # Check if it's a status with a green dot
            if key.lower() == 'status':
                value_html = f'<span class="text-green-700">\u25cf {value}</span>'
            else:
                value_html = f'<span>{value}</span>'
            focus_lines.append(
                f'                        <li class="flex justify-between pt-1">\n'
                f'                            <span>{key}</span>\n'
                f'                            {value_html}\n'
                f'                        </li>'
            )
        else:
            focus_lines.append(
                f'                        <li class="flex justify-between border-b border-stone-200 pb-2">\n'
                f'                            <span>{key}</span>\n'
                f'                            <span>{value}</span>\n'
                f'                        </li>'
            )
    focus_html = '\n'.join(focus_lines)

    return f"""    <!-- Philosophy / About -->
    <section id="about" class="py-20 border-t border-stone-200 relative z-10 bg-stone-50/80 backdrop-blur-sm">
        <div class="max-w-5xl mx-auto px-6 grid grid-cols-1 md:grid-cols-12 gap-12">
            <div class="md:col-span-4">
                <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400">{label}</h2>
            </div>
            <div class="md:col-span-8 space-y-8">
                <blockquote class="font-serif text-2xl italic text-stone-800 border-l-2 border-stone-900 pl-6 py-1">
                    \u201c{quote}\u201d
                </blockquote>

                <div class="prose prose-stone text-stone-600">
{paragraphs_html}
                </div>

                <!-- Current Status Box -->
                <div class="bg-stone-100 p-6 border border-stone-200 mt-8">
                    <h3 class="font-mono text-xs font-bold uppercase text-stone-500 mb-4">Current Focus</h3>
                    <ul class="space-y-3 font-mono text-sm text-stone-700">
{focus_html}
                    </ul>
                </div>
            </div>
        </div>
    </section>"""


def build_roles(data):
    body = data['Roles']
    label = get_simple_value(body, 'Label')
    roles = get_all_subsections_at(body, level=3)

    cards = []
    for i, (name, content) in enumerate(roles):
        # Parse font preference
        font_match = re.match(r'^font:\s*(\w+)\s*\n', content)
        font = 'serif'
        if font_match:
            font = font_match.group(1)
            content = content[font_match.end():].strip()

        num = f'{i + 1:02d}'
        description = content.strip()

        if font == 'mono':
            title_html = f'<h3 class="font-mono text-xl text-stone-900 mb-4 font-medium">{name}</h3>'
        else:
            title_html = f'<h3 class="font-serif text-2xl text-stone-900 mb-4">{name}</h3>'

        cards.append(f"""                <!-- {name.replace('The ', '')} -->
                <div class="bg-stone-50 p-10 hover:bg-white transition-colors">
                    <div class="mb-4 text-stone-400">{num}</div>
                    {title_html}
                    <p class="text-stone-600 leading-relaxed text-sm">
                        {description}
                    </p>
                </div>""")

    cards_html = '\n\n' + '\n\n'.join(cards) + '\n'

    return f"""    <!-- Roles Grid -->
    <section id="roles" class="py-20 border-t border-stone-200 relative z-10 bg-stone-50">
        <div class="max-w-5xl mx-auto px-6">
            <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-12">{label}</h2>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-px bg-stone-200 border border-stone-200">{cards_html}            </div>
        </div>
    </section>"""


def build_resume(data):
    body = data['Resume']
    label = get_simple_value(body, 'Label')
    subtitle = get_simple_value(body, 'Subtitle')
    pdf_link = get_simple_value(body, 'PDF Link')

    # Parse skills
    skills_body = get_subsection(body, 'Skills')
    skill_groups = get_all_subsections_at(skills_body, level=3)

    skills_html_parts = []
    for group_name, group_content in skill_groups:
        items = parse_list_items(group_content)
        badges = []
        for item in items:
            m = re.match(r'^(.+?)\s*\[(\w+)\]$', item)
            if m:
                name = m.group(1).strip()
                level = m.group(2)
            else:
                name = item
                level = 'primary'

            if level == 'primary':
                badges.append(
                    f'                            <span class="px-3 py-1 bg-white border border-stone-200 text-stone-700 text-xs font-mono rounded shadow-sm">{name}</span>'
                )
            else:
                badges.append(
                    f'                            <span class="px-3 py-1 bg-stone-100 border border-stone-200 text-stone-500 text-xs font-mono rounded">{name}</span>'
                )

        badges_html = '\n'.join(badges)
        skills_html_parts.append(f"""                    <div>
                        <span class="font-serif text-stone-400 italic text-sm mr-4">{group_name}</span>
                        <div class="inline-flex flex-wrap gap-2">
{badges_html}
                        </div>
                    </div>""")

    skills_html = '\n\n'.join(skills_html_parts)

    # Parse experience cards
    experience_body = get_subsection(body, 'Experience')
    experiences = get_all_subsections_at(experience_body, level=3)

    cards = []
    modal_entries = []

    for exp_name, exp_content in experiences:
        meta, card_description = parse_metadata_lines(exp_content)

        exp_id = meta.get('id', '')
        tag = meta.get('tag', '')
        role = meta.get('role', '')
        date = meta.get('date', '')

        # Split card description from detail section
        detail_split = re.split(r'^#### Detail\s*$', card_description, flags=re.MULTILINE)
        card_text = detail_split[0].strip()
        detail_body = detail_split[1].strip() if len(detail_split) > 1 else ''

        # Parse detail: overview paragraph, key contributions, tech
        detail_paragraphs = []
        detail_contributions = []
        detail_tech = []

        if detail_body:
            # Overview is text before first #####
            overview_split = re.split(r'^##### ', detail_body, flags=re.MULTILINE)
            overview = overview_split[0].strip()
            detail_paragraphs = [p.strip() for p in overview.split('\n\n') if p.strip()]

            # Parse ##### sections
            for j in range(1, len(overview_split)):
                section_text = overview_split[j]
                section_lines = section_text.strip().split('\n', 1)
                section_name = section_lines[0].strip()
                section_content = section_lines[1].strip() if len(section_lines) > 1 else ''

                if section_name == 'Key Contributions':
                    detail_contributions = parse_list_items(section_content)
                elif section_name == 'Tech':
                    detail_tech = parse_list_items(section_content)

        # Build modal detail entry
        contributions_html = '\n'.join(
            f'                        <li>{c}</li>' for c in detail_contributions
        )
        tech_html = '\n'.join(
            f'                        <span class="px-2 py-1 bg-stone-100 text-xs font-mono">{t}</span>'
            for t in detail_tech
        )
        overview_html = '\n'.join(
            f'                    <p class="mb-4 text-stone-600">{p}</p>' for p in detail_paragraphs
        )

        # Modal role/date can differ from card display
        modal_role = meta.get('modal_role', role)
        modal_date = date
        card_date = meta.get('card_date', date)

        escaped_name = exp_name.replace("'", "\\'")
        modal_entries.append(f"""            '{exp_id}': {{
                title: '{escaped_name}',
                role: '{modal_role}',
                date: '{modal_date}',
                content: `
                    <h4 class="font-bold mb-2">Overview</h4>
{overview_html}

                    <h4 class="font-bold mb-2">Key Contributions</h4>
                    <ul class="list-disc pl-5 space-y-2 text-stone-600 mb-6">
{contributions_html}
                    </ul>
                    <div class="flex gap-2">
{tech_html}
                    </div>
                `
            }}""")

        # Build experience card HTML
        card_role_line = role + ' \u2022 ' + card_date if card_date != 'none' else role
        cards.append(f"""                <!-- Card -->
                <button onclick="openDetail('{exp_id}')" class="text-left group bg-white border border-stone-200 p-8 hover:shadow-lg hover:-translate-y-1 transition-all duration-300 relative overflow-hidden">
                    <div class="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                        <i class="fa-solid fa-arrow-right -rotate-45 text-stone-400"></i>
                    </div>
                    <span class="inline-block px-2 py-1 bg-stone-100 text-stone-500 font-mono text-[10px] uppercase tracking-wider mb-4">{tag}</span>
                    <h3 class="font-serif text-xl text-stone-900 group-hover:text-stone-600 transition-colors">{exp_name}</h3>
                    <p class="font-mono text-xs text-stone-500 mt-1 mb-4">{card_role_line}</p>
                    <p class="text-stone-600 text-sm leading-relaxed line-clamp-3">
                        {card_text}
                    </p>
                </button>""")

    cards_html = '\n\n'.join(cards)
    modals_js = ',\n'.join(modal_entries)

    resume_html = f"""    <!-- Live Resume Section -->
    <section id="resume" class="py-20 border-t border-stone-200 relative z-10 bg-stone-50/80 backdrop-blur-sm">
        <div class="max-w-5xl mx-auto px-6">
            <div class="flex justify-between items-end mb-12">
                <div>
                    <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400">{label}</h2>
                    <p class="font-serif text-3xl text-stone-900 mt-2">{subtitle}</p>
                </div>
                <a href="{pdf_link}" target="_blank" class="hidden md:inline-flex items-center gap-2 text-stone-500 hover:text-stone-900 transition-colors font-mono text-xs border border-stone-300 px-3 py-2 rounded-sm bg-white">
                    <i class="fa-solid fa-file-pdf"></i> View PDF
                </a>
            </div>

            <!-- Skills Cards -->
            <div class="mb-16">
                <h3 class="font-mono text-xs font-bold uppercase text-stone-500 mb-6 border-b border-stone-200 pb-2">Proficiencies</h3>

                <div class="space-y-6">
{skills_html}
                </div>
            </div>

            <!-- Experience Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

{cards_html}

            </div>
        </div>
    </section>"""

    return resume_html, modals_js


def build_society(data):
    body = data['Society']
    label = get_simple_value(body, 'Label')
    content_raw = get_simple_value(body, 'Content')
    cta_raw = get_simple_value(body, 'CTA')

    paragraphs = [p.strip() for p in content_raw.split('\n\n') if p.strip()]

    # Parse CTA
    cta_meta, _ = parse_metadata_lines(cta_raw)
    cta_text = cta_meta.get('text', 'Send Introduction')
    cta_email = cta_meta.get('email', '')

    paras_html = []
    for i, p in enumerate(paragraphs):
        if i == 0:
            paras_html.append(
                f'                <p class="font-serif text-lg text-stone-900 mb-4 leading-relaxed">\n'
                f'                    {p}\n'
                f'                </p>'
            )
        else:
            paras_html.append(
                f'                <p class="text-stone-600 text-lg leading-relaxed mb-8">\n'
                f'                    {p}\n'
                f'                </p>'
            )

    paras_html_str = '\n'.join(paras_html)

    return f"""    <!-- The Society / Call to Action -->
    <section id="society" class="py-20 border-t border-stone-200 bg-stone-100 relative z-10">
        <div class="max-w-5xl mx-auto px-6">
            <div class="max-w-3xl">
                <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-6">{label}</h2>
{paras_html_str}
                <a href="mailto:{cta_email}" class="inline-flex items-center gap-2 text-stone-900 font-medium border-b border-stone-900 pb-1 hover:text-stone-600 hover:border-stone-600 transition-colors">
                    {cta_text} <i class="fa-solid fa-arrow-right -rotate-45 text-sm"></i>
                </a>
            </div>
        </div>
    </section>"""


def build_projects(data):
    body = data['Projects']
    label = get_simple_value(body, 'Label')
    projects = get_all_subsections_at(body, level=3)

    items = []
    for i, (name, content) in enumerate(projects):
        meta, description = parse_metadata_lines(content)
        subtitle = meta.get('subtitle', '')
        tags_str = meta.get('tags', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        is_last = (i == len(projects) - 1)
        border_class = 'border-t border-b' if is_last else 'border-t'

        tags_html = '\n'.join(
            f'                        <span class="text-xs font-mono bg-white border border-stone-200 px-2 py-1 text-stone-600">{t}</span>'
            for t in tags
        )

        items.append(f"""                <!-- Project -->
                <div class="group py-8 {border_class} border-stone-200 flex flex-col md:flex-row gap-6 md:items-start hover:bg-stone-100 transition-colors px-4 -mx-4">
                    <div class="md:w-1/4">
                        <h3 class="font-serif text-xl text-stone-900 group-hover:underline decoration-1 underline-offset-4">{name}</h3>
                        <span class="font-mono text-xs text-stone-500 mt-1 block">{subtitle}</span>
                    </div>
                    <div class="md:w-2/4">
                        <p class="text-stone-600 leading-relaxed text-sm">
                            {description}
                        </p>
                    </div>
                    <div class="md:w-1/4 text-right md:text-right flex gap-2 justify-end">
{tags_html}
                    </div>
                </div>""")

    items_html = '\n\n'.join(items)

    return f"""    <!-- Projects List -->
    <section id="projects" class="py-20 border-t border-stone-200 relative z-10 bg-stone-50">
        <div class="max-w-5xl mx-auto px-6">
            <div class="flex items-baseline justify-between mb-12">
                <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400">{label}</h2>
            </div>

            <div class="space-y-0">
{items_html}
            </div>
        </div>
    </section>"""


def build_footer(data):
    body = data['Footer']
    contact_raw = get_simple_value(body, 'Contact')
    theme_text = get_simple_value(body, 'Theme')
    quote = get_simple_value(body, 'Quote')

    # Parse contact links
    contact_meta, _ = parse_metadata_lines(contact_raw)
    github_url = contact_meta.get('github', '#')
    github_label = contact_meta.get('github_label', 'GitHub')
    email_label = contact_meta.get('email', '[Email Address]')
    linkedin_label = contact_meta.get('linkedin', 'LinkedIn')

    return f"""    <!-- Footer -->
    <section id="contact" class="py-20 bg-stone-900 text-stone-400 relative z-10">
        <div class="max-w-5xl mx-auto px-6 grid grid-cols-1 md:grid-cols-2 gap-12">
            <div>
                <h2 class="font-serif text-2xl text-stone-50 mb-6">Contact</h2>
                <div class="space-y-4">
                    <a href="{github_url}" target="_blank" class="block hover:text-white transition-colors flex items-center gap-3">
                        <i class="fa-brands fa-github"></i> {github_label}
                    </a>
                    <a href="#" class="block hover:text-white transition-colors flex items-center gap-3">
                        <i class="fa-solid fa-envelope"></i> {email_label}
                    </a>
                    <a href="#" class="block hover:text-white transition-colors flex items-center gap-3">
                        <i class="fa-brands fa-linkedin"></i> {linkedin_label}
                    </a>
                </div>
            </div>
            <div class="md:text-right flex flex-col justify-end">
                <p class="font-mono text-xs uppercase tracking-wide text-stone-500 mb-2">
                    {theme_text}
                </p>
                <p class="font-serif text-lg italic text-stone-300">
                    \u201c{quote}\u201d
                </p>
            </div>
        </div>
    </section>"""


def build_modal_js(modals_js):
    return f"""    <!-- Content for Modals -->
    <script>
        const resumeDetails = {{
{modals_js}
        }};

        function openDetail(key) {{
            const data = resumeDetails[key];
            const content = document.getElementById('detail-content');
            const overlay = document.getElementById('detail-overlay');

            content.innerHTML = `
                <h2 class="font-serif text-3xl text-stone-900 mb-2">${{data.title}}</h2>
                <p class="font-mono text-stone-500 mb-8 border-b border-stone-100 pb-4">${{data.role}} \u2022 ${{data.date}}</p>
                <div class="prose prose-stone">
                    ${{data.content}}
                </div>
            `;

            overlay.classList.remove('invisible', 'opacity-0');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden'; // Prevent scrolling background
        }}

        function closeDetail() {{
            const overlay = document.getElementById('detail-overlay');
            overlay.classList.add('invisible', 'opacity-0');
            overlay.classList.remove('active');
            document.body.style.overflow = ''; // Restore scrolling
        }}

        // Close on escape key
        document.addEventListener('keydown', function(event) {{
            if (event.key === "Escape") {{
                closeDetail();
            }}
        }});

        // Close on clicking outside modal
        document.getElementById('detail-overlay').addEventListener('click', function(e) {{
            if (e.target === this) {{
                closeDetail();
            }}
        }});
    </script>"""


def build_planes_js():
    with open('js/paper-planes.js', 'r', encoding='utf-8') as f:
        content = f.read()
    return f"""    <!-- Script for Paper Airplanes -->
    <script>
{content}
    </script>"""


def main():
    data = parse_content('content.md')

    resume_html, modals_js = build_resume(data)

    parts = [
        build_head(),
        '',
        build_nav(),
        '',
        build_modal(),
        '',
        build_hero(data),
        '',
        build_about(data),
        '',
        build_roles(data),
        '',
        resume_html,
        '',
        build_society(data),
        '',
        build_projects(data),
        '',
        build_footer(data),
        '',
        build_planes_js(),
        '',
        build_modal_js(modals_js),
        '</body>',
        '</html>',
        '',
    ]

    output = '\n'.join(parts)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(output)

    print('Built index.html successfully.')


if __name__ == '__main__':
    main()
