"""Small decorative supermarket illustrations for the workspace headings."""
from html import escape

import streamlit as st


# Static SVG artwork inherits each module's palette from the shared stylesheet.
ILLUSTRATIONS = {
    'inventory': '''
        <path class="market-wash" d="M24 74C8 44 31 13 65 18S132 6 143 41S123 90 88 85S39 98 24 74Z"/>
        <path d="M27 24V83M133 24V83M23 53H137M23 79H137"/>
        <rect class="market-product" x="36" y="29" width="19" height="24" rx="3"/>
        <path d="M41 29V24H50V29M41 39H50"/>
        <path class="market-product" d="M67 53V34L73 28H85L91 34V53Z"/>
        <path d="M67 34H91M79 28V34M73 43H85"/>
        <rect class="market-product" x="103" y="35" width="21" height="18" rx="4"/>
        <path d="M107 31H120M108 43H119"/>
        <rect class="market-product" x="36" y="64" width="40" height="15" rx="3"/>
        <path d="M42 64C39 54 49 55 51 64M54 64C51 54 61 55 63 64M66 64C63 54 73 55 74 64"/>
        <rect class="market-product" x="90" y="60" width="15" height="19" rx="3"/>
        <rect class="market-product" x="110" y="60" width="15" height="19" rx="3"/>
        <path d="M94 67H101M114 67H121M35 87H125"/>
    ''',
    'purchasing': '''
        <path class="market-wash" d="M24 68C8 43 36 13 66 19S129 6 142 38S126 89 91 85S41 95 24 68Z"/>
        <path class="market-product" d="M48 46V29L54 23H69L75 29V46Z"/>
        <path d="M48 29H75M62 23V29M54 37H66"/>
        <path class="market-product" d="M89 46C80 37 81 29 88 29C92 29 93 32 96 32C99 32 101 29 105 30C113 32 110 41 105 46Z"/>
        <path d="M96 32C95 25 101 22 106 23C105 29 101 31 96 32"/>
        <path class="market-product" d="M34 47H126L116 79H44Z"/>
        <rect x="30" y="43" width="100" height="7" rx="3"/>
        <path d="M53 43L68 17M107 43L92 17M56 58L59 70M72 58V70M88 58V70M104 58L101 70M44 87H116"/>
    ''',
    'receiving': '''
        <path class="market-wash" d="M19 67C9 38 38 15 71 21S130 7 143 39S121 92 87 84S30 97 19 67Z"/>
        <rect class="market-product" x="33" y="46" width="53" height="34" rx="3"/>
        <path d="M53 46V58H66V46M41 70H51M45 66V74"/>
        <rect class="market-product" x="61" y="19" width="49" height="27" rx="3"/>
        <path d="M80 19V30H91V19M99 37H103"/>
        <path d="M122 40V76C122 80 119 82 115 82H91M122 40H131"/>
        <rect class="market-product" x="91" y="53" width="25" height="23" rx="2"/>
        <path d="M99 53V61H107V53"/>
        <circle class="market-product" cx="116" cy="86" r="5"/>
        <path d="M29 88H101"/>
    ''',
    'history': '''
        <path class="market-wash" d="M23 72C10 43 34 13 65 19S128 8 141 36S127 89 92 85S38 96 23 72Z"/>
        <path class="market-product" d="M51 16H108V83L101 79L94 83L87 79L80 83L73 79L66 83L59 79L51 83Z"/>
        <path d="M63 28H96M63 36H87M63 48H79M91 48H96M63 56H79M91 56H96M63 65H96"/>
        <path d="M64 71V75M68 71V75M75 71V75M78 71V75M84 71V75M91 71V75M95 71V75"/>
        <circle class="market-product" cx="115" cy="63" r="16"/>
        <path d="M115 53V63L122 67M36 88H126"/>
    ''',
}


def workspace_header(title, description, module):
    """Render a semantic heading with non-interactive, screen-reader-hidden art."""
    artwork = ILLUSTRATIONS[module]
    markup = (
        '<section class="workspace-heading">'
        f'<div class="workspace-heading-copy"><h2>{escape(title)}</h2>'
        f'<p>{escape(description)}</p></div>'
        '<svg class="market-illustration" viewBox="0 0 160 100" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
        f'{artwork}</svg></section>'
    )
    st.markdown(markup, unsafe_allow_html=True)


def supermarket_border(position):
    """Frame the workspace with quiet, decorative supermarket aisle scenes."""
    if position not in ('top', 'bottom'):
        raise ValueError('Border position must be top or bottom.')
    # Alternate the scenes so the two edges feel related without being identical.
    modules = (('inventory', 'purchasing', 'receiving', 'inventory', 'purchasing', 'receiving')
               if position == 'top' else
               ('purchasing', 'inventory', 'receiving', 'purchasing', 'inventory', 'receiving'))
    positions = (15, 185, 355, 715, 885, 1055)
    scenes = ''.join(
        f'<g transform="translate({x}, 8) scale(.78)">{ILLUSTRATIONS[module]}</g>'
        for x, module in zip(positions, modules)
    )
    storefront = '''
        <g transform="translate(536, 8)">
        <path class="market-wash" d="M-12 72Q-28 5 56 10T137 72Z"/>
        <path class="market-product" d="M8 33H120V76H8Z"/>
        <path class="market-product" d="M7 17H121L130 34H-2Z"/>
        <path d="M7 17H121M23 17L18 34M43 17L40 34M64 17V34M85 17L88 34M105 17L110 34"/>
        <path d="M-2 34V39Q8 48 18 39Q29 48 40 39Q52 48 64 39Q76 48 88 39Q99 48 110 39Q120 48 130 39V34"/>
        <rect x="19" y="51" width="34" height="18" rx="2"/>
        <rect x="73" y="51" width="33" height="25" rx="2"/>
        <path d="M90 51V76M84 63V66M96 63V66M-5 80H134"/>
        <path d="M26 62C23 55 31 55 34 62C37 55 45 55 44 62M24 64H47"/>
        </g>
    '''
    markup = (
        f'<div class="supermarket-border supermarket-border--{position}" aria-hidden="true">'
        '<svg viewBox="0 0 1200 100" xmlns="http://www.w3.org/2000/svg" '
        'preserveAspectRatio="xMidYMid meet" focusable="false">'
        '<path class="market-floor" d="M0 88H1200"/>'
        f'{scenes}{storefront}</svg></div>'
    )
    st.markdown(markup, unsafe_allow_html=True)
