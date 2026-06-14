# Sensor Pinout — Raspberry Pi 5 GPIO Header

Standard 40-pin header. Pin 1 is marked with a square pad on the Pi.

```
                     3V3  (1) (2)  5V
        SDA1  GPIO  2  (3) (4)  5V
        SCL1  GPIO  3  (5) (6)  GND
        1-Wire GPIO 4  (7) (8)  GPIO 14   UART TX
                  GND  (9) (10) GPIO 15   UART RX
   LED-G   GPIO 17 (11) (12) GPIO 18      (reserved I2S)
   LED-A   GPIO 27 (13) (14) GND
   LED-R   GPIO 22 (15) (16) GPIO 23      HOTSPOT-RESET
                  3V3 (17) (18) GPIO 24   DRIVE-ACT-IN
        SPI MOSI GPIO 10 (19) (20) GND
        SPI MISO GPIO 9  (21) (22) GPIO 25 (spare)
        SPI SCLK GPIO 11 (23) (24) GPIO 8  CE0
                  GND (25) (26) GPIO 7    CE1
              ID_SD (27) (28) ID_SC       (reserved EEPROM)
                  GPIO 5  (29) (30) GND
                  GPIO 6  (31) (32) GPIO 12
                  GPIO 13 (33) (34) GND
                  GPIO 19 (35) (36) GPIO 16
                  GPIO 26 (37) (38) GPIO 20
                     GND (39) (40) GPIO 21
```

## Connections in use

| Function          | GPIO | Pin | Direction | Notes                       |
|-------------------|------|-----|-----------|-----------------------------|
| I2C1 SDA          | 2    | 3   | bidir     | Sensor bus                  |
| I2C1 SCL          | 3    | 5   | bidir     | Sensor bus                  |
| 1-Wire (DS18B20)  | 4    | 7   | bidir     | Optional probe ports        |
| LED — heartbeat   | 17   | 11  | out       | Green, active high          |
| LED — sync        | 27   | 13  | out       | Amber, active high          |
| LED — fault       | 22   | 15  | out       | Red, active high            |
| Hotspot reset     | 23   | 16  | out       | Drives opto-FET, active high|
| Drive activity in | 24   | 18  | in        | From drive's activity LED   |

## Power pins consumed

- **Pin 1 (3V3)**: feeds sensor backplane (≤ 500 mA budget)
- **Pin 2 (5V)**: NOT used — Pi gets 5 V via USB-C PD only
- **Pin 6, 9, 14, 20, 25, 30, 34, 39 (GND)**: pick the closest GND to
  each load for ground returns

## Reserved / do-not-use

- **GPIO 14/15 (UART)**: left available for serial console / GPS HAT.
- **GPIO 18 / 19 (I2S)**: reserved for future audio (mushroom-room
  ambient acoustic monitoring) — do not repurpose.
- **ID_SD / ID_SC (pins 27/28)**: HAT EEPROM bus — leave alone.

## Sensor backplane connector

The sensor backplane uses a 6-pin JST-XH connector at the Pi end. Pinout
on the cable, viewed into the connector from the wire side:

| Pin | Wire color | Net    | GPIO header pin |
|-----|------------|--------|-----------------|
| 1   | red        | 3V3    | 1               |
| 2   | black      | GND    | 9               |
| 3   | yellow     | SDA    | 3               |
| 4   | green      | SCL    | 5               |
| 5   | blue       | 1-Wire | 7               |
| 6   | white      | reserve| (no connect)    |

Keep cable length ≤ 200 mm and twist SDA+GND and SCL+GND as pairs.
