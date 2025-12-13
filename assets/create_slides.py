#!/usr/bin/env python3
"""
Two stunning slides for Fraud Detection presentation
Slide 1: World map with London-Tokyo impossible travel
Slide 2: Agent explanation with tool flow
"""

from PIL import Image, ImageDraw, ImageFont
import math

WIDTH = 1920
HEIGHT = 1080

# Color palette
WHITE = (255, 255, 255, 255)
LIGHT_TEXT = (220, 220, 230, 255)
MUTED = (120, 130, 150, 255)
ACCENT_GREEN = (16, 185, 129, 255)
ACCENT_RED = (239, 68, 68, 255)
ACCENT_BLUE = (59, 130, 246, 255)
ACCENT_CYAN = (34, 211, 238, 255)
ACCENT_AMBER = (251, 191, 36, 255)
ACCENT_PURPLE = (168, 85, 247, 255)
DARK_CARD = (20, 30, 50, 200)
GRID_COLOR = (40, 60, 90, 80)

FONT_DIR = "/Users/dirien/.claude/plugins/cache/anthropic-agent-skills/example-skills/00756142ab04/skills/canvas-design/canvas-fonts"

def load_fonts():
    fonts = {}
    try:
        fonts['hero'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Bold.ttf", 72)
        fonts['big'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Bold.ttf", 48)
        fonts['title'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Bold.ttf", 32)
        fonts['subtitle'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Regular.ttf", 24)
        fonts['body'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Regular.ttf", 20)
        fonts['small'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Regular.ttf", 16)
        fonts['mono'] = ImageFont.truetype(f"{FONT_DIR}/JetBrainsMono-Regular.ttf", 16)
        fonts['mono_bold'] = ImageFont.truetype(f"{FONT_DIR}/JetBrainsMono-Bold.ttf", 14)
        fonts['tag'] = ImageFont.truetype(f"{FONT_DIR}/JetBrainsMono-Bold.ttf", 12)
        fonts['time'] = ImageFont.truetype(f"{FONT_DIR}/JetBrainsMono-Bold.ttf", 28)
        fonts['huge'] = ImageFont.truetype(f"{FONT_DIR}/InstrumentSans-Bold.ttf", 120)
    except Exception as e:
        print(f"Font error: {e}")
        default = ImageFont.load_default()
        for k in ['hero', 'big', 'title', 'subtitle', 'body', 'small', 'mono',
                  'mono_bold', 'tag', 'time', 'huge']:
            fonts[k] = default
    return fonts

def draw_world_map_grid(draw):
    """Draw a stylized world map grid"""
    # Horizontal latitude lines
    for lat in range(0, HEIGHT, 80):
        for x in range(0, WIDTH, 8):
            if x % 16 < 8:
                draw.point((x, lat), fill=GRID_COLOR)

    # Vertical longitude lines
    for lon in range(0, WIDTH, 120):
        for y in range(0, HEIGHT, 8):
            if y % 16 < 8:
                draw.point((lon, y), fill=GRID_COLOR)

    # Draw simplified continent outlines (dots pattern)
    # Europe region
    for i in range(50):
        x = 700 + (i % 10) * 15 + (hash(i) % 10)
        y = 350 + (i // 10) * 12 + (hash(i*2) % 8)
        draw.ellipse([x-2, y-2, x+2, y+2], fill=(50, 70, 100, 100))

    # Asia region
    for i in range(80):
        x = 1100 + (i % 15) * 20 + (hash(i*3) % 15)
        y = 300 + (i // 15) * 15 + (hash(i*4) % 10)
        draw.ellipse([x-2, y-2, x+2, y+2], fill=(50, 70, 100, 100))

def draw_location_marker(draw, x, y, label, time_str, color, fonts, pulse=True):
    """Draw an animated-style location marker"""
    # Outer pulse rings
    if pulse:
        for r in [60, 45, 30]:
            alpha = int(255 * (1 - r/70))
            draw.ellipse([x-r, y-r, x+r, y+r], outline=color, width=2)

    # Inner solid dot
    draw.ellipse([x-15, y-15, x+15, y+15], fill=color)
    draw.ellipse([x-8, y-8, x+8, y+8], fill=WHITE)

    # Label card
    label_width = len(label) * 12 + 40
    card_x = x - label_width // 2
    card_y = y + 70

    # Card background
    draw.rounded_rectangle([card_x, card_y, card_x + label_width, card_y + 70],
                          radius=12, fill=DARK_CARD)

    # City name
    draw.text((card_x + 20, card_y + 10), label, font=fonts['body'], fill=WHITE)
    # Time
    draw.text((card_x + 20, card_y + 38), time_str, font=fonts['time'], fill=color)

def draw_flight_path(draw, x1, y1, x2, y2, color):
    """Draw a curved flight path"""
    # Calculate control point for bezier curve
    cx = (x1 + x2) / 2
    cy = min(y1, y2) - 150

    points = []
    for t in range(101):
        t = t / 100
        px = (1-t)**2 * x1 + 2*(1-t)*t * cx + t**2 * x2
        py = (1-t)**2 * y1 + 2*(1-t)*t * cy + t**2 * y2
        points.append((px, py))

    # Draw the path with varying thickness
    for i in range(len(points) - 1):
        progress = i / len(points)
        width = int(3 + 4 * math.sin(progress * math.pi))
        draw.line([points[i], points[i+1]], fill=color, width=width)

    return points[len(points)//2]

def draw_x_marker(draw, x, y, size, color):
    """Draw a bold X marker"""
    draw.line([(x-size, y-size), (x+size, y+size)], fill=color, width=8)
    draw.line([(x-size, y+size), (x+size, y-size)], fill=color, width=8)

def create_slide1():
    """Slide 1: World Map with Impossible Travel"""
    img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    # Draw world map grid
    draw_world_map_grid(draw)

    # Define city positions (approximate on our grid)
    london_x, london_y = 720, 380
    tokyo_x, tokyo_y = 1450, 400

    # Draw the flight path
    mid_point = draw_flight_path(draw, london_x, london_y, tokyo_x, tokyo_y, ACCENT_RED)

    # Draw X at midpoint
    mx, my = mid_point

    # Glow effect behind X
    for r in range(40, 10, -5):
        alpha = int(80 * (1 - r/40))
        glow_color = (239, 68, 68, alpha)
        draw.ellipse([mx-r, my-r, mx+r, my+r], fill=glow_color)

    draw_x_marker(draw, mx, my, 25, ACCENT_RED)

    # Location markers
    draw_location_marker(draw, london_x, london_y, "LONDON", "09:00", ACCENT_GREEN, fonts)
    draw_location_marker(draw, tokyo_x, tokyo_y, "TOKYO", "09:15", ACCENT_RED, fonts)

    # Title at top
    draw.text((80, 60), "Impossible Travel Detected", font=fonts['hero'], fill=WHITE)

    # Subtitle
    draw.text((80, 150), "Credit card used in two locations 9,500 km apart — in just 15 minutes",
              font=fonts['subtitle'], fill=MUTED)

    # Bottom info card
    card_y = HEIGHT - 200
    draw.rounded_rectangle([80, card_y, 700, card_y + 140], radius=16, fill=DARK_CARD)

    draw.text((110, card_y + 20), "TRANSACTION BLOCKED", font=fonts['tag'], fill=ACCENT_RED)
    draw.text((110, card_y + 45), "User: user_123", font=fonts['mono'], fill=LIGHT_TEXT)
    draw.text((110, card_y + 70), "Amount: $2,000 • Electronics Store", font=fonts['mono'], fill=LIGHT_TEXT)
    draw.text((110, card_y + 95), "Ticket: TICKET-999", font=fonts['mono'], fill=ACCENT_AMBER)

    # Stats on bottom right
    stats_x = WIDTH - 400
    draw.rounded_rectangle([stats_x, card_y, stats_x + 320, card_y + 140], radius=16, fill=DARK_CARD)

    draw.text((stats_x + 30, card_y + 15), "ANALYSIS", font=fonts['tag'], fill=ACCENT_CYAN)
    draw.text((stats_x + 30, card_y + 45), "Distance: 9,500 km", font=fonts['body'], fill=LIGHT_TEXT)
    draw.text((stats_x + 30, card_y + 75), "Time: 15 minutes", font=fonts['body'], fill=LIGHT_TEXT)
    draw.text((stats_x + 30, card_y + 105), "Verdict: IMPOSSIBLE", font=fonts['body'], fill=ACCENT_RED)

    output = "/Users/dirien/conductor/workspaces/from-works-on-my-machine-to-production-ready-ai-agents-with-amazon-bedrock-agent-core/lome/local-prototype/assets/slide1-world-map.png"
    img.save(output, 'PNG')
    print(f"Created: {output}")

def draw_tool_card(draw, x, y, num, name, desc, color, fonts):
    """Draw a tool execution card"""
    width = 500
    height = 100

    draw.rounded_rectangle([x, y, x + width, y + height], radius=12, fill=DARK_CARD, outline=color, width=2)

    # Number circle
    draw.ellipse([x + 20, y + 25, x + 70, y + 75], fill=color)
    draw.text((x + 37, y + 35), str(num), font=fonts['title'], fill=WHITE)

    # Tool name
    draw.text((x + 90, y + 25), name, font=fonts['mono_bold'], fill=color)
    # Description
    draw.text((x + 90, y + 55), desc, font=fonts['small'], fill=MUTED)

def draw_arrow_down(draw, x, y, length, color):
    """Draw a downward arrow"""
    draw.line([(x, y), (x, y + length)], fill=color, width=3)
    draw.polygon([(x, y + length + 10), (x - 8, y + length), (x + 8, y + length)], fill=color)

def create_slide2():
    """Slide 2: Agent Architecture and Flow"""
    img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fonts = load_fonts()

    # Title
    draw.text((80, 50), "AI-Powered Fraud Detection", font=fonts['hero'], fill=WHITE)
    draw.text((80, 140), "Strands SDK Agent with Claude Opus 4.5 on Amazon Bedrock",
              font=fonts['subtitle'], fill=MUTED)

    # Tech badges
    badges = [("Strands SDK", ACCENT_BLUE), ("Claude Opus 4.5", ACCENT_PURPLE),
              ("Amazon Bedrock", ACCENT_AMBER), ("us-east-1", ACCENT_CYAN)]
    badge_x = WIDTH - 600
    for badge, color in badges:
        w = len(badge) * 10 + 30
        draw.rounded_rectangle([badge_x, 60, badge_x + w, 90], radius=6, outline=color, width=2)
        draw.text((badge_x + 15, 66), badge, font=fonts['tag'], fill=color)
        badge_x += w + 15

    # Left side: Agent visualization
    agent_x = 150
    agent_y = 280

    # Agent box
    draw.rounded_rectangle([agent_x, agent_y, agent_x + 350, agent_y + 450],
                          radius=20, fill=DARK_CARD, outline=ACCENT_PURPLE, width=3)

    draw.text((agent_x + 30, agent_y + 25), "FRAUD ANALYST AGENT", font=fonts['tag'], fill=ACCENT_PURPLE)

    # Robot/AI icon (simple geometric)
    icon_x = agent_x + 175
    icon_y = agent_y + 130
    # Head
    draw.rounded_rectangle([icon_x - 40, icon_y - 50, icon_x + 40, icon_y + 10],
                          radius=10, outline=ACCENT_PURPLE, width=3)
    # Eyes
    draw.ellipse([icon_x - 25, icon_y - 35, icon_x - 10, icon_y - 20], fill=ACCENT_CYAN)
    draw.ellipse([icon_x + 10, icon_y - 35, icon_x + 25, icon_y - 20], fill=ACCENT_CYAN)
    # Antenna
    draw.line([(icon_x, icon_y - 50), (icon_x, icon_y - 70)], fill=ACCENT_PURPLE, width=3)
    draw.ellipse([icon_x - 6, icon_y - 80, icon_x + 6, icon_y - 68], fill=ACCENT_AMBER)

    # Agent capabilities
    caps = [
        "• Analyzes transactions in real-time",
        "• Detects impossible travel patterns",
        "• Executes protective actions",
        "• Documents reasoning & decisions"
    ]
    cap_y = agent_y + 180
    for cap in caps:
        draw.text((agent_x + 30, cap_y), cap, font=fonts['small'], fill=LIGHT_TEXT)
        cap_y += 35

    # Powered by
    draw.text((agent_x + 30, agent_y + 380), "Powered by", font=fonts['tag'], fill=MUTED)
    draw.text((agent_x + 30, agent_y + 405), "Claude Opus 4.5", font=fonts['body'], fill=WHITE)

    # Right side: Tool execution flow
    tools_x = 600
    tools_y = 280

    draw.text((tools_x, tools_y - 40), "TOOL EXECUTION FLOW", font=fonts['tag'], fill=ACCENT_CYAN)

    tools = [
        (1, "get_user_profile()", "Fetches user data and home location", ACCENT_BLUE),
        (2, "get_recent_transactions()", "Gets last known transaction", ACCENT_CYAN),
        (3, "block_credit_card()", "Blocks card and creates ticket", ACCENT_RED),
    ]

    for i, (num, name, desc, color) in enumerate(tools):
        ty = tools_y + i * 140
        draw_tool_card(draw, tools_x, ty, num, name, desc, color, fonts)

        if i < len(tools) - 1:
            draw_arrow_down(draw, tools_x + 250, ty + 100, 25, MUTED)

    # Decision output
    decision_y = tools_y + 430
    draw.rounded_rectangle([tools_x, decision_y, tools_x + 500, decision_y + 120],
                          radius=12, fill=(40, 20, 20, 200), outline=ACCENT_RED, width=3)

    draw.text((tools_x + 30, decision_y + 15), "DECISION", font=fonts['tag'], fill=ACCENT_RED)
    draw.text((tools_x + 30, decision_y + 45), "BLOCK CARD", font=fonts['big'], fill=ACCENT_RED)
    draw.text((tools_x + 30, decision_y + 95), "Fraud prevented • Customer protected", font=fonts['small'], fill=ACCENT_GREEN)

    # Right side: The scenario recap
    recap_x = 1200
    recap_y = 280

    draw.text((recap_x, recap_y - 40), "THE SCENARIO", font=fonts['tag'], fill=ACCENT_AMBER)

    draw.rounded_rectangle([recap_x, recap_y, recap_x + 620, recap_y + 500],
                          radius=16, fill=DARK_CARD)

    # Timeline
    events = [
        ("09:00", "London, UK", "John Doe buys coffee", ACCENT_GREEN, "Normal transaction"),
        ("09:15", "Tokyo, JP", "$2,000 at Electronics Store", ACCENT_RED, "Suspicious!"),
    ]

    event_y = recap_y + 30
    for time, location, action, color, note in events:
        # Time badge
        draw.rounded_rectangle([recap_x + 30, event_y, recap_x + 110, event_y + 40],
                              radius=6, fill=color)
        draw.text((recap_x + 42, event_y + 8), time, font=fonts['mono_bold'], fill=WHITE)

        # Location and action
        draw.text((recap_x + 130, event_y + 5), location, font=fonts['body'], fill=WHITE)
        draw.text((recap_x + 130, event_y + 30), action, font=fonts['small'], fill=MUTED)
        draw.text((recap_x + 400, event_y + 12), note, font=fonts['tag'], fill=color)

        event_y += 90

        if time == "09:00":
            # Draw connecting line
            draw.line([(recap_x + 70, event_y - 40), (recap_x + 70, event_y + 5)],
                     fill=MUTED, width=2)

    # Analysis
    analysis_y = event_y + 30
    draw.line([(recap_x + 30, analysis_y), (recap_x + 590, analysis_y)], fill=MUTED, width=1)

    draw.text((recap_x + 30, analysis_y + 20), "AGENT ANALYSIS", font=fonts['tag'], fill=ACCENT_CYAN)

    findings = [
        "✗ Distance: 9,500 km between transactions",
        "✗ Time elapsed: Only 15 minutes",
        "✗ Minimum flight time: ~12 hours",
        "✗ High-risk merchant: Electronics",
    ]

    find_y = analysis_y + 50
    for finding in findings:
        draw.text((recap_x + 30, find_y), finding, font=fonts['small'], fill=LIGHT_TEXT)
        find_y += 28

    # Verdict
    draw.text((recap_x + 30, find_y + 20), "VERDICT: IMPOSSIBLE TRAVEL", font=fonts['body'], fill=ACCENT_RED)

    output = "/Users/dirien/conductor/workspaces/from-works-on-my-machine-to-production-ready-ai-agents-with-amazon-bedrock-agent-core/lome/local-prototype/assets/slide2-agent.png"
    img.save(output, 'PNG')
    print(f"Created: {output}")

if __name__ == "__main__":
    create_slide1()
    create_slide2()
    print("\nBoth slides created!")
