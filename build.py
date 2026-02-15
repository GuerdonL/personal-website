#!/usr/bin/env python3
"""
Build script for Guerdon's personal website.
Parses content.md and assembles index.html as a 2D spatial metro map.
"""

import re
import html


# ─── Station Coordinates (left, top in px on the 4000x3000 world) ────────────

STATION_COORDS = {
    'hero':             (2150, 1200),
    'writings':         (800,  700),
    'poetry':           (550,  100),
    'about-me':         (900,  1900),
    'resume':           (3300, 700),
    'society-projects': (2500, 2700),
}


# ─── Parsing Helpers ─────────────────────────────────────────────────────────

def parse_content(filepath):
    """Parse content.md into structured sections."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    raw_sections = re.split(r'\n---\n', text)
    sections = {}

    for raw in raw_sections:
        raw = raw.strip()
        if not raw:
            continue
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
    """Extract content under a heading of given level."""
    prefix = '#' * level
    stop_patterns = '|'.join(rf'^{"#" * i} ' for i in range(1, level + 1))
    pattern = rf'^{prefix} {re.escape(heading)}\s*\n(.*?)(?={stop_patterns}|\Z)'
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''


def get_all_subsections(body, level=2):
    """Get all subsections at a given heading level as (name, content) pairs."""
    prefix = '#' * level
    pattern = rf'^{prefix} (.+)$'
    parts = re.split(pattern, body, flags=re.MULTILINE)
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
    """Get the text content under a simple heading."""
    prefix = '#' * level
    pattern = rf'^{prefix} {re.escape(heading)}\s*\n(.*?)(?=^#+\s|\Z)'
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''


def escape(text):
    """Escape HTML entities in text."""
    return html.escape(text)


def station_style(station_id):
    """Return inline style for absolute positioning of a station."""
    x, y = STATION_COORDS[station_id]
    return f'left:{x}px; top:{y}px;'


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


# ─── Metro line colors ───────────────────────────────────────────────────────
LINE_COLORS = {
    'writer':     '#D64045',
    'programmer': '#2A9D8F',
    'activist':   '#7B6D8D',
}


def build_hero(data):
    body = data['Hero']
    title = get_simple_value(body, 'Title')
    description = get_simple_value(body, 'Description')

    # Role tags become clickable metro line triggers
    tag_defs = [
        ('Writer',     'writer',     LINE_COLORS['writer'],     'writings'),
        ('Programmer', 'programmer', LINE_COLORS['programmer'], 'resume'),
        ('Activist',   'activist',   LINE_COLORS['activist'],   'about-me'),
    ]

    tags_html = '\n'.join(
        f'                    <button onclick="panTo(\'{dest}\')" '
        f'class="group px-4 py-2 border-2 rounded-sm font-mono text-xs uppercase tracking-wide '
        f'text-stone-500 hover:text-stone-900 transition-all cursor-pointer flex items-center gap-2" '
        f'style="border-color: {color};">'
        f'<span class="inline-block w-3 h-3 rounded-full" style="background: {color};"></span>'
        f'{name}</button>'
        for name, line_id, color, dest in tag_defs
    )

    sx = station_style('hero')

    return f"""    <!-- Hero Station (Central Hub) -->
    <section id="hero" class="station-wide" style="{sx}">
        <div class="min-h-[500px] flex flex-col justify-center px-6 pt-16">
            <div class="max-w-3xl space-y-8">
                <h1 class="font-serif text-5xl md:text-6xl leading-tight font-medium text-stone-900">
                    {title}
                </h1>

                <div class="space-y-6">
                    <p class="font-sans text-lg text-stone-600 max-w-2xl leading-relaxed">
                        {description}
                    </p>

                    <div class="flex flex-wrap gap-3 pt-4">
{tags_html}
                    </div>
                </div>
            </div>
        </div>
    </section>"""


def build_about_me(data):
    """Combined About Me station — philosophy + contact in a two-column layout."""
    body = data['About']
    label = get_simple_value(body, 'Label')
    quote = get_simple_value(body, 'Quote')
    content_raw = get_simple_value(body, 'Content')
    focus_raw = get_simple_value(body, 'Current Focus')
    closing_quote = get_simple_value(body, 'Closing Quote')
    theme_text = get_simple_value(body, 'Theme')

    # Contact info
    contact_raw = get_simple_value(body, 'Contact')
    contact_meta, _ = parse_metadata_lines(contact_raw)
    github_url = contact_meta.get('github', '#')
    github_label = contact_meta.get('github_label', 'GitHub')
    email_label = contact_meta.get('email', '[Email Address]')
    linkedin_label = contact_meta.get('linkedin', 'LinkedIn')

    # Philosophy paragraphs
    paragraphs = [p.strip() for p in content_raw.split('\n\n') if p.strip()]
    paragraphs_html = '\n'.join(
        f'                            <p class="leading-relaxed">\n                                {p}\n                            </p>'
        for p in paragraphs
    )

    # Current focus metadata
    focus_items = []
    for line in focus_raw.split('\n'):
        m = re.match(r'^- (.+?):\s*(.+)$', line)
        if m:
            focus_items.append((m.group(1).strip(), m.group(2).strip()))

    focus_lines = []
    for i, (key, value) in enumerate(focus_items):
        is_last = (i == len(focus_items) - 1)
        if is_last and key.lower() == 'status':
            value_html = f'<span class="text-green-700">\u25cf {value}</span>'
        else:
            value_html = f'<span>{value}</span>'

        border_cls = '' if is_last else ' border-b border-stone-200 pb-2'
        pad_cls = 'pt-1' if is_last else ''
        focus_lines.append(
            f'                                <li class="flex justify-between{border_cls} {pad_cls}">\n'
            f'                                    <span>{key}</span>\n'
            f'                                    {value_html}\n'
            f'                                </li>'
        )
    focus_html = '\n'.join(focus_lines)

    sx = station_style('about-me')

    return f"""    <!-- About Me Station -->
    <section id="about-me" class="station-wide" style="{sx}">
        <div class="py-12 px-6 bg-stone-50/80 backdrop-blur-sm border border-stone-200">
            <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-8">{label}</h2>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <!-- Left: Philosophy -->
                <div class="space-y-6">
                    <blockquote class="font-serif text-2xl italic text-stone-800 border-l-2 border-stone-900 pl-6 py-1">
                        \u201c{quote}\u201d
                    </blockquote>

                    <div class="prose prose-stone text-stone-600">
{paragraphs_html}
                    </div>

                    <div class="bg-stone-100 p-6 border border-stone-200">
                        <h3 class="font-mono text-xs font-bold uppercase text-stone-500 mb-4">Current Focus</h3>
                        <ul class="space-y-3 font-mono text-sm text-stone-700">
{focus_html}
                        </ul>
                    </div>
                </div>

                <!-- Right: Contact -->
                <div class="bg-stone-900 text-stone-400 p-8 border border-stone-700 flex flex-col justify-between">
                    <div>
                        <h3 class="font-serif text-2xl text-stone-50 mb-6">Contact</h3>
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
                    <div class="mt-8">
                        <p class="font-mono text-xs uppercase tracking-wide text-stone-500 mb-2">
                            {theme_text}
                        </p>
                        <p class="font-serif text-lg italic text-stone-300">
                            \u201c{closing_quote}\u201d
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </section>"""


def build_writings(data):
    body = data['Writings']
    label = get_simple_value(body, 'Label')
    substack_text = get_simple_value(body, 'Substack')

    # Parse poems from ### subsections under ## Poetry
    poetry_body = get_subsection(body, 'Poetry')
    poems = get_all_subsections_at(poetry_body, level=3)

    poems_html_parts = []
    for title, text in poems:
        lines = text.strip().split('\n')
        lines_html = '<br>\n'.join(f'                        {l}' for l in lines)
        poems_html_parts.append(f"""                <div class="border border-stone-200 p-6 bg-white">
                    <h4 class="font-serif text-lg text-stone-900 mb-3">{title}</h4>
                    <p class="font-serif text-sm text-stone-600 leading-relaxed italic">
{lines_html}
                    </p>
                </div>""")

    poems_html = '\n\n'.join(poems_html_parts)

    sx = station_style('writings')

    return f"""    <!-- Writings Station -->
    <section id="writings" class="station" style="{sx}">
        <div class="py-12 px-6 bg-stone-50/80 backdrop-blur-sm border border-stone-200">
            <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-8">{label}</h2>

            <!-- Substack CTA -->
            <div class="bg-stone-100 border border-stone-200 p-6 mb-8">
                <p class="font-serif text-lg text-stone-900 mb-4">{substack_text}</p>
                <a href="#" class="inline-flex items-center gap-2 text-stone-900 font-medium border-b border-stone-900 pb-1 hover:text-stone-600 hover:border-stone-600 transition-colors font-mono text-xs uppercase tracking-wide">
                    Subscribe <i class="fa-solid fa-arrow-right -rotate-45 text-sm"></i>
                </a>
            </div>

            <!-- Poetry Grid -->
            <div class="space-y-4">
{poems_html}
            </div>
        </div>
    </section>"""


def build_poetry(data):
    """Poetry station — a lighter station linking to the full writings."""
    sx = station_style('poetry')

    body = data['Writings']
    poetry_body = get_subsection(body, 'Poetry')
    poems = get_all_subsections_at(poetry_body, level=3)

    # Show just the first poem as a teaser
    if poems:
        title, text = poems[0]
        lines = text.strip().split('\n')
        lines_html = '<br>\n'.join(f'                    {l}' for l in lines)
        poem_html = f"""            <div class="border border-stone-200 p-6 bg-white mb-4">
                <h4 class="font-serif text-lg text-stone-900 mb-3">{title}</h4>
                <p class="font-serif text-sm text-stone-600 leading-relaxed italic">
{lines_html}
                </p>
            </div>"""
    else:
        poem_html = ''

    return f"""    <!-- Poetry Station -->
    <section id="poetry" class="station" style="{sx}">
        <div class="py-12 px-6 bg-stone-50/80 backdrop-blur-sm border border-stone-200">
            <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-6">Selected Poetry</h2>
{poem_html}
            <button onclick="panTo('writings')" class="font-mono text-xs text-stone-500 hover:text-stone-900 transition-colors uppercase tracking-wide">
                View all writings <i class="fa-solid fa-arrow-right text-xs"></i>
            </button>
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

        detail_split = re.split(r'^#### Detail\s*$', card_description, flags=re.MULTILINE)
        card_text = detail_split[0].strip()
        detail_body = detail_split[1].strip() if len(detail_split) > 1 else ''

        detail_paragraphs = []
        detail_contributions = []
        detail_tech = []

        if detail_body:
            overview_split = re.split(r'^##### ', detail_body, flags=re.MULTILINE)
            overview = overview_split[0].strip()
            detail_paragraphs = [p.strip() for p in overview.split('\n\n') if p.strip()]

            for j in range(1, len(overview_split)):
                section_text = overview_split[j]
                section_lines = section_text.strip().split('\n', 1)
                section_name = section_lines[0].strip()
                section_content = section_lines[1].strip() if len(section_lines) > 1 else ''

                if section_name == 'Key Contributions':
                    detail_contributions = parse_list_items(section_content)
                elif section_name == 'Tech':
                    detail_tech = parse_list_items(section_content)

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

    sx = station_style('resume')

    resume_html = f"""    <!-- Resume Station -->
    <section id="resume" class="station-wide" style="{sx}">
        <div class="py-12 px-6 bg-stone-50/80 backdrop-blur-sm border border-stone-200">
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


def build_society_projects(data):
    """Combined Society + Projects station."""
    # Society part
    soc_body = data['Society']
    soc_label = get_simple_value(soc_body, 'Label')
    soc_content_raw = get_simple_value(soc_body, 'Content')
    cta_raw = get_simple_value(soc_body, 'CTA')
    cta_meta, _ = parse_metadata_lines(cta_raw)
    cta_text = cta_meta.get('text', 'Send Introduction')
    cta_email = cta_meta.get('email', '')

    soc_paragraphs = [p.strip() for p in soc_content_raw.split('\n\n') if p.strip()]
    soc_paras_html = []
    for i, p in enumerate(soc_paragraphs):
        if i == 0:
            soc_paras_html.append(
                f'                <p class="font-serif text-lg text-stone-900 mb-4 leading-relaxed">{p}</p>'
            )
        else:
            soc_paras_html.append(
                f'                <p class="text-stone-600 text-lg leading-relaxed mb-8">{p}</p>'
            )
    soc_paras_str = '\n'.join(soc_paras_html)

    # Projects part
    proj_body = data['Projects']
    proj_label = get_simple_value(proj_body, 'Label')
    projects = get_all_subsections_at(proj_body, level=3)

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

        items.append(f"""                <div class="group py-6 {border_class} border-stone-200 hover:bg-stone-100 transition-colors px-4 -mx-4">
                    <div class="flex flex-col gap-3">
                        <div>
                            <h3 class="font-serif text-lg text-stone-900 group-hover:underline decoration-1 underline-offset-4">{name}</h3>
                            <span class="font-mono text-xs text-stone-500 mt-1 block">{subtitle}</span>
                        </div>
                        <p class="text-stone-600 leading-relaxed text-sm">{description}</p>
                        <div class="flex gap-2">
{tags_html}
                        </div>
                    </div>
                </div>""")

    items_html = '\n\n'.join(items)

    sx = station_style('society-projects')

    return f"""    <!-- Society & Projects Station -->
    <section id="society-projects" class="station" style="{sx}">
        <div class="py-12 px-6 bg-stone-50/80 backdrop-blur-sm border border-stone-200">
            <!-- Society -->
            <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-6">{soc_label}</h2>
{soc_paras_str}
            <a href="mailto:{cta_email}" class="inline-flex items-center gap-2 text-stone-900 font-medium border-b border-stone-900 pb-1 hover:text-stone-600 hover:border-stone-600 transition-colors mb-12 block">
                {cta_text} <i class="fa-solid fa-arrow-right -rotate-45 text-sm"></i>
            </a>

            <!-- Projects -->
            <h2 class="font-sans text-sm font-bold uppercase tracking-wider text-stone-400 mb-6 mt-8">{proj_label}</h2>
            <div class="space-y-0">
{items_html}
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
            document.body.style.overflow = 'hidden';
        }}

        function closeDetail() {{
            const overlay = document.getElementById('detail-overlay');
            overlay.classList.add('invisible', 'opacity-0');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }}

        // Close on escape key (only if modal is open)
        document.addEventListener('keydown', function(event) {{
            if (event.key === "Escape") {{
                const overlay = document.getElementById('detail-overlay');
                if (overlay && !overlay.classList.contains('invisible')) {{
                    closeDetail();
                }}
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


def build_metro_js():
    with open('js/metro.js', 'r', encoding='utf-8') as f:
        content = f.read()
    return f"""    <!-- Metro Lines -->
    <script>
{content}
    </script>"""


def build_map_nav_js():
    with open('js/map-nav.js', 'r', encoding='utf-8') as f:
        content = f.read()
    return f"""    <!-- Map Navigation -->
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
        '    <!-- Paper Plane Canvas (fixed viewport) -->',
        '    <canvas id="planes-canvas" class="fixed top-0 left-0 w-screen h-screen pointer-events-none z-0 opacity-40"></canvas>',
        '',
        '    <!-- Metro Viewport -->',
        '    <div id="metro-viewport">',
        '        <div id="metro-world">',
        '',
        build_hero(data),
        '',
        build_about_me(data),
        '',
        build_writings(data),
        '',
        build_poetry(data),
        '',
        resume_html,
        '',
        build_society_projects(data),
        '',
        '        </div>',
        '    </div>',
        '',
        build_planes_js(),
        '',
        build_metro_js(),
        '',
        build_map_nav_js(),
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
