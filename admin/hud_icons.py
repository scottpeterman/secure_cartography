def get_router_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100" style="color: var(--icon-color, #000000); background: var(--icon-bg, transparent)">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="0.3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" stroke-width="2" filter="url(#glow)"/>
  <g stroke="currentColor" stroke-width="2" filter="url(#glow)">
    <path d="M30,30 L70,70" fill="none"/>
    <polygon points="35,25 25,35 25,25" fill="currentColor"/>
    <polygon points="75,65 65,75 75,75" fill="currentColor"/>
    <path d="M70,30 L30,70" fill="none"/>
    <polygon points="65,25 75,35 75,25" fill="currentColor"/>
    <polygon points="25,65 35,75 25,75" fill="currentColor"/>
  </g>
</svg>'''

def get_switch_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" style="color: var(--icon-color, #000000); background: var(--icon-bg, transparent)">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="0.3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect x="20" y="20" width="60" height="60" rx="4"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        filter="url(#glow)"/>
  <g stroke="currentColor" stroke-width="2" filter="url(#glow)">
    <line x1="35" y1="35" x2="65" y2="35"/>
    <polygon points="60,32 65,35 60,38" fill="currentColor"/>
    <polygon points="40,32 35,35 40,38" fill="currentColor"/>
    <line x1="35" y1="65" x2="65" y2="65"/>
    <polygon points="60,62 65,65 60,68" fill="currentColor"/>
    <polygon points="40,62 35,65 40,68" fill="currentColor"/>
  </g>
</svg>'''

def get_firewall_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" style="color: var(--icon-color, #000000); background: var(--icon-bg, transparent)">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="0.3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <circle cx="50" cy="50" r="48" fill="none" stroke="currentColor" stroke-width="2" filter="url(#glow)"/>
  <polygon points="35,30 65,50 35,70" fill="currentColor" filter="url(#glow)"/>
  <rect x="70" y="30" width="4" height="40" fill="currentColor" filter="url(#glow)"/>
</svg>'''


def get_discovering_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 41">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="0.3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <g fill="none" stroke="#22D3EE" stroke-width="0.8" filter="url(#glow)">
    <!-- Base cylinder outlines -->
    <path d="M29.137 22.837c16.144 0 29.137-5.119 29.137-11.419S45.281 0 29.137 0 0 5.119 0 11.419s12.994 11.419 29.137 11.419z" opacity="0.4"/>
    <path d="M58.274 11.419c0 6.3-12.994 11.419-29.137 11.419S0 17.719 0 11.419v16.537c0 6.3 12.994 11.419 29.137 11.419s29.137-5.119 29.137-11.419z" opacity="0.4"/>

    <!-- Scanning line -->
    <line x1="0" y1="20" x2="60" y2="20" opacity="0.6">
      <animateTransform
        attributeName="transform"
        type="translate"
        from="0 -20"
        to="0 41"
        dur="2s"
        repeatCount="indefinite"/>
    </line>

    <!-- Pulsing circles -->
    <circle cx="30" cy="20" r="25" opacity="0.4">
      <animate
        attributeName="r"
        values="20;30"
        dur="1.5s"
        repeatCount="indefinite"/>
      <animate
        attributeName="opacity"
        values="0.4;0"
        dur="1.5s"
        repeatCount="indefinite"/>
    </circle>
    <circle cx="30" cy="20" r="25" opacity="0.4">
      <animate
        attributeName="r"
        values="20;30"
        dur="1.5s"
        begin="0.5s"
        repeatCount="indefinite"/>
      <animate
        attributeName="opacity"
        values="0.4;0"
        dur="1.5s"
        begin="0.5s"
        repeatCount="indefinite"/>
    </circle>

    <!-- Corner brackets -->
    <path d="M2 2 h6 M2 2 v6" stroke-width="1"/>
    <path d="M58 2 h-6 M58 2 v6" stroke-width="1"/>
    <path d="M2 39 h6 M2 39 v-6" stroke-width="1"/>
    <path d="M58 39 h-6 M58 39 v-6" stroke-width="1"/>
  </g>
</svg>'''


def get_unknown_svg():
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 41">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="0.3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <g fill="none" stroke="#22D3EE" stroke-width="0.8" filter="url(#glow)">
    <!-- Base outline - simplified generic network device -->
    <rect x="10" y="8" width="40" height="25" rx="2" opacity="0.4"/>

    <!-- Question mark -->
    <path d="M25 28h2v2h-2zM31 16c0-3-2.5-5-5.5-5S20 13 20 16h2c0-2 1.5-3 3.5-3s3.5 1 3.5 3c0 1-1 2-2.5 3-2 1.5-2.5 2.5-2.5 4h2c0-1 .5-2 2-3 2-1.5 3-2.5 3-4z" 
          opacity="0.8"/>

    <!-- Corner brackets -->
    <path d="M2 2 h6 M2 2 v6" stroke-width="1"/>
    <path d="M58 2 h-6 M58 2 v6" stroke-width="1"/>
    <path d="M2 39 h6 M2 39 v-6" stroke-width="1"/>
    <path d="M58 39 h-6 M58 39 v-6" stroke-width="1"/>
  </g>
</svg>'''