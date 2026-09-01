"""The shared scenes of every Crowe Sense film, and the three variants that wrap them.

A scene is (id, eyebrow, headline, body_lines, voice). The voice text is written to be read
aloud by XTTS: numbers spelled, no part numbers, no URLs. Cards show the terse version.
"""
SPINE = [
  dict(id="what", eyebrow="The node", headline="A sensing node for a growing room",
       body=["Raspberry Pi 5, four Sensirion and Bosch sensors", "under a louvered radiation shield", "3D-printed housing, about $280 in parts"],
       art="cad",
       voice="Crowe Sense is a sensing node for a growing room. A Raspberry Pi five, four Sensirion and Bosch sensors under a louvered radiation shield, a three D printed housing, about two hundred and eighty dollars in parts. It reads carbon dioxide, temperature, humidity, light and volatile compounds, and it keeps every reading on the node."),
  dict(id="path", eyebrow="One contract", headline="Six surfaces read the same numbers",
       body=["node to relay, signed", "desktop, web, phone, Cortex, terminal, any screen"],
       art="path",
       voice="A signed copy of every reading goes to a relay, so the same numbers show up in the desktop app, the web app, the phone, Cortex, the terminal, and any screen in the room. One contract, six surfaces."),
  dict(id="dash", eyebrow="What the grower sees", headline="The room, live",
       body=["temperature, humidity, carbon dioxide, VPD", "flow hood and controller health", "shown here with demonstration data"],
       art="dash",
       voice="This is what a grower sees. Temperature, humidity, carbon dioxide and vapor pressure deficit for every room, the flow hood, and the health of the controller itself. The numbers on this screen are demonstration data; the real ones come from the pilot."),
  dict(id="envelope", eyebrow="Judged against practice", headline="43 condition bands, each cited to a clip",
       body=["extracted from 68 of the founder's cultivation videos", "a band needs two independent statements to judge anything"],
       art="report",
       voice="Readings are judged against forty three condition bands taken from my own cultivation videos, each cited to the clip it came from. A band needs two independent statements before it judges anything. Nobody else can ship that layer, because nobody else has the corpus."),
  dict(id="proven", eyebrow="Built and tested", headline="105 tests, all green",
       body=["firmware 51, relay 7, CLI 25, desktop 14, Cortex 8", "parts list priced live", "enclosure is a parametric model, ready to print"],
       art="tests",
       voice="The software is built and tested end to end. One hundred and five tests across the firmware, the relay and the apps, all green. The parts list is priced. The enclosure is a parametric model ready to print."),
  dict(id="notproven", eyebrow="Said plainly", headline="No node has run in a room yet",
       body=["the pilot: 25 nodes in 10 growers' rooms", "every node's first week passes a provenance test", "before anyone calls it working"],
       art="none",
       voice="What is not proven is the room. No node has yet run with physical sensors in a growing room. The pilot changes that. Twenty five nodes in ten growers' rooms, and every node's first week of data passes a provenance test before anyone calls it working."),
  dict(id="founder", eyebrow="Who is building it", headline="Michael Crowe",
       body=["growing mushrooms since 2005, about ten years commercially", "about 195,000 subscribers on Southwest Mushrooms", "built every surface in this film"],
       art="founder",
       voice="I have grown mushrooms since two thousand five, about ten of those years commercially, and roughly one hundred ninety five thousand people follow the channel where I teach it. I built every surface you just saw."),
]
ASK_INVESTOR = dict(id="ask", eyebrow="The ask", headline="$175,000 on a SAFE",
       body=["hardware and people only; cloud and analytics on credits", "day 30: five nodes in real rooms", "day 90: 25 nodes at ten growers", "day 180: twenty labelled harvests"],
       art="ask",
       voice="The raise is one hundred seventy five thousand dollars on a SAFE. Cloud and analytics are already covered by credits, so the money is hardware and people. Day thirty, five nodes in real rooms. Day ninety, twenty five nodes at ten growers. Day one eighty, twenty labelled harvests.")
ASK_PROGRAM = dict(id="ask", eyebrow="The budget", headline="$175,000 pilot",
       body=["25 nodes, a contract hardware engineer, a year of the founder's time", "cloud and analytics on credits already held", "day 30, day 90, day 180 milestones, each with its proof"],
       art="ask",
       voice="The pilot budget is one hundred seventy five thousand dollars. Twenty five nodes, a contract hardware engineer, and a year of the founder's time. Cloud and analytics are covered by credits the company already holds. Every milestone carries its own proof.")
def open_scene(target, voice, line):
    return dict(id="open", eyebrow="For " + target, headline=line, body=[], art="none", voice=voice)
def close_scene(voice, line, contact=True):
    return dict(id="close", eyebrow="Next", headline=line, body=["michael@crowelogic.com", "crowelogic.com", "youtube.com/@SouthwestMushrooms"] if contact else ["github.com/MichaelCrowe11/crowe-sense", "youtube.com/@SouthwestMushrooms"], art="close",
                voice=voice + " Michael Crowe, Crowe Logic, Phoenix.")
TITLE = dict(id="title", eyebrow="Crowe Logic", headline="Crowe Sense", body=[], art="title", voice="Crowe Sense.")

YOUTUBE = dict(
  open=dict(voice="This is the sensor I have been building for grow rooms, and the software around it is done. Here is what it is, what it is not yet, and how you can get one in your room.",
            line="The sensor I built for grow rooms"),
  close=dict(voice="The code, the firmware and the enclosure are public on GitHub, under Michael Crowe eleven, crowe sense. If you run rooms and want a node in one of them for the pilot, the link is in the description.",
             line="Public on GitHub. Pilot rooms wanted."),
  ask=None)
HARRISON = dict(
  open=dict(voice="Harry, this is the sensor half of what I bring to the building. Two minutes.",
            line="The sensor half of what I bring"),
  close=dict(voice="Your rooms are the first place these go. When you are ready, I put two nodes in the existing rooms this month, and we write the readings into the lender package as measured, not projected.",
             line="Two nodes in your rooms this month"),
  ask=ASK_PROGRAM)
