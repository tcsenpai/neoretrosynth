import pyxel
import struct
import numpy as np
from scipy.io import wavfile

# Cyberpunk color palette
pyxel.COLOR_NEON_PINK = 14
pyxel.COLOR_NEON_BLUE = 12
pyxel.COLOR_NEON_GREEN = 11
pyxel.COLOR_NEON_YELLOW = 10

class NeoRetroSynth:
    def __init__(self):
        pyxel.init(360, 360, title="NeoRetro Synth - Cyberpunk Edition")
        self.current_octave = 2
        self.loop_recording = False
        self.loop = []
        self.sound_length = 10
        self.playing = False
        self.waveforms = ['T', 'S', 'P', 'N']  # Triangle, Square, Pulse, Noise
        self.current_waveform = 0
        self.drum_patterns = [
            [[0, 0, 100, 0.25] for _ in range(32)] for _ in range(2)
        ]
        self.synth_patterns = [
            [[0, 0, 0, 0, 100, 0.25] for _ in range(32)] for _ in range(2)
        ]
        self.drum_lengths = [8, 8]
        self.synth_lengths = [8, 8]
        self.current_steps = [0, 0, 0, 0]  # 2 drum tracks, 2 synth tracks
        self.sequencer_playing = False
        self.edit_mode = False
        self.edit_position = 0  # column
        self.edit_target = 0  # 0-1 for drums, 2-3 for synths
        self.drum_sounds = ["K", "S", "H", "O"]  # Kick, Snare, Hi-hat, Open hi-hat
        self.synth_notes = ["C", "D", "E", "F", "G", "A", "B", "C+"]
        self.bpm = 120  # Default BPM
        self.frame_count = 0  # Custom frame counter for BPM-based timing
        self.drum_volume = 7  # Range 0-7
        self.synth_volume = 7  # Range 0-7
        self.presets = {}
        self.arpeggiator_on = False
        self.arp_pattern = [0, 4, 7, 12]  # Simple arpeggiator pattern
        
        # Add these assertions
        assert 0 <= self.synth_volume <= 7, f"Synth volume out of range: {self.synth_volume}"
        assert 1 <= self.sound_length <= 99, f"Sound length out of range: {self.sound_length}"
        assert 0 <= self.current_waveform < len(self.waveforms), f"Invalid waveform index: {self.current_waveform}"
        
        self.setup_sounds()
        
        # Add this test sound
        pyxel.sounds[63].set("C2", "T", "7", "F", 30)
        pyxel.play(0, 63)
        
        pyxel.run(self.update, self.draw)

    def setup_sounds(self):
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        for octave in range(0, 5):  # 5 octaves, 0-4
            for i, note in enumerate(notes):
                sound_index = octave * 12 + i
                if sound_index < 60:  # Ensure we don't exceed the valid range
                    pyxel.sounds[sound_index].set(
                        f"{note}{octave}",
                        self.waveforms[self.current_waveform],
                        "7",
                        "N",
                        self.sound_length
                    )
                    print(f"Set sound {sound_index}: {note}{octave}, {self.waveforms[self.current_waveform]}, 7, N, {self.sound_length}")
        
        # Drum sounds
        pyxel.sounds[60].set(
            "A0",  # Lower pitch for a deeper kick
            "N",   # Noise waveform for a more percussive sound
            f"{self.drum_volume}543210",  # Use drum_volume
            "F",   # Frequency sweep from high to low
            5      # Short duration
        )
        pyxel.sounds[61].set("F3", "N", "7", "S", 5)  # Snare
        pyxel.sounds[62].set("F#4", "N", "7", "S", 3)  # Hi-hat closed
        pyxel.sounds[63].set("C#4", "N", "7", "S", 10)  # Hi-hat open

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        self.handle_keyboard_input()
        self.handle_drum_input()
        self.handle_loop_controls()
        self.handle_sound_controls()
        self.handle_sequencer()

        if pyxel.btnp(pyxel.KEY_F1):
            self.export_to_midi()
        if pyxel.btnp(pyxel.KEY_F2):
            self.export_to_wav()
        if pyxel.btnp(pyxel.KEY_F3):
            self.save_preset("default")
        if pyxel.btnp(pyxel.KEY_F4):
            self.load_preset("default")
        if pyxel.btnp(pyxel.KEY_F5):
            self.toggle_arpeggiator()

    def handle_keyboard_input(self):
        keys = [
            pyxel.KEY_Z, pyxel.KEY_S, pyxel.KEY_X, pyxel.KEY_D, 
            pyxel.KEY_C, pyxel.KEY_V, pyxel.KEY_G, pyxel.KEY_B, 
            pyxel.KEY_H, pyxel.KEY_N, pyxel.KEY_J, pyxel.KEY_M
        ]
        for i, key in enumerate(keys):
            if pyxel.btnp(key):
                note = i % 8  # Ensure note is within 0-7 range
                print(f"Key pressed: {i}, Note: {note}, Octave: {self.current_octave}")
                if self.arpeggiator_on:
                    for arp_note in self.apply_arpeggiator(note):
                        self.play_note(arp_note, self.current_octave)
                        if self.loop_recording:
                            self.loop.append((0, arp_note, self.current_octave, self.current_waveform))
                else:
                    self.play_note(note, self.current_octave)
                    if self.loop_recording:
                        self.loop.append((0, note, self.current_octave, self.current_waveform))
                        
    def play_note(self, note, octave, waveform=None, velocity=100, duration=0.25, channel=0):
        assert channel in [0, 1], f"Invalid channel: {channel}"
        note_name = self.synth_notes[note % 8]
        if note_name == "C+":
            note_name = "C"
            octave += 1
        
        sound_index = note + (octave - 1) * 12
        sound_index = min(sound_index, 59)  # Ensure we don't exceed the highest note
        
        if waveform is None:
            waveform = self.current_waveform
        
        # Add error checking for waveform
        waveform = max(0, min(waveform, len(self.waveforms) - 1))
        
        volume = str(min(int(velocity / 14), 7))  # Convert velocity to Pyxel's volume range (0-7)
        
        pyxel.sounds[sound_index].set(
            f"{note_name}{octave}",
            self.waveforms[waveform],
            volume,
            "N",
            int(duration * 30)  # Convert duration to Pyxel's time units
        )
        print(f"Playing note: {note_name}{octave} on channel {channel}")
        print(f"Sound {sound_index} set to: {note_name}{octave}, {self.waveforms[waveform]}, {volume}, N, {int(duration * 30)}")
        pyxel.play(channel, sound_index, loop=False)

    def handle_loop_controls(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.loop_recording = not self.loop_recording
            if not self.loop_recording and self.loop:
                self.playing = True
        
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.playing = not self.playing
        
        if pyxel.btnp(pyxel.KEY_C):
            self.loop.clear()
            self.playing = False

        if self.playing and self.loop:
            if pyxel.frame_count % 6 == 0:  # Adjust timing as needed
                channel, sound = self.loop[pyxel.frame_count // 6 % len(self.loop)]
                pyxel.play(channel, sound)

    def handle_sound_controls(self):
        if pyxel.btnp(pyxel.KEY_UP) and self.current_octave < 4:
            self.current_octave += 1
        if pyxel.btnp(pyxel.KEY_DOWN) and self.current_octave > 1:
            self.current_octave -= 1
        
        if pyxel.btnp(pyxel.KEY_LEFT) and self.sound_length > 1:
            self.sound_length -= 1
            self.setup_sounds()
        if pyxel.btnp(pyxel.KEY_RIGHT) and self.sound_length < 99:
            self.sound_length += 1
            self.setup_sounds()
        
        if pyxel.btnp(pyxel.KEY_W):
            self.current_waveform = (self.current_waveform + 1) % len(self.waveforms)
            self.setup_sounds()

        if pyxel.btnp(pyxel.KEY_PERIOD):
            self.increase_bpm()
        if pyxel.btnp(pyxel.KEY_COMMA):
            self.decrease_bpm()

        if pyxel.btnp(pyxel.KEY_6):
            self.decrease_drum_volume()
        if pyxel.btnp(pyxel.KEY_7):
            self.increase_drum_volume()

        if pyxel.btnp(pyxel.KEY_8):
            self.decrease_synth_volume()
        if pyxel.btnp(pyxel.KEY_9):
            self.increase_synth_volume()

    def increase_bpm(self):
        self.bpm = min(self.bpm + 5, 300)  # Cap at 300 BPM

    def decrease_bpm(self):
        self.bpm = max(self.bpm - 5, 60)  # Minimum 60 BPM

    def increase_drum_volume(self):
        self.drum_volume = min(self.drum_volume + 1, 7)
        self.setup_sounds()

    def decrease_drum_volume(self):
        self.drum_volume = max(self.drum_volume - 1, 0)
        self.setup_sounds()

    def increase_synth_volume(self):
        self.synth_volume = min(self.synth_volume + 1, 7)

    def decrease_synth_volume(self):
        self.synth_volume = max(self.synth_volume - 1, 0)

    def handle_sequencer(self):
        if pyxel.btnp(pyxel.KEY_TAB):
            self.sequencer_playing = not self.sequencer_playing
            self.frame_count = 0  # Reset frame count when toggling sequencer

        frames_per_step = 3600 // self.bpm  # 60 seconds * 60 frames per second / BPM
        
        if self.sequencer_playing:
            self.frame_count += 1
            if self.frame_count >= frames_per_step:
                self.frame_count = 0
                for i in range(2):  # For each drum track
                    if self.drum_patterns[i][self.current_steps[i]][0]:
                        sound_index, velocity, duration = self.drum_patterns[i][self.current_steps[i]][1:]
                        pyxel.play(1, 60 + sound_index, loop=False)
                        if self.loop_recording:
                            self.loop.append((1, 60 + sound_index))
                    self.current_steps[i] = (self.current_steps[i] + 1) % self.drum_lengths[i]
                
                for i in range(2):  # For each synth track
                    if self.synth_patterns[i][self.current_steps[i+2]][0]:
                        note, octave, waveform, velocity, duration = self.synth_patterns[i][self.current_steps[i+2]][1:]
                        self.play_note(note, octave, waveform, velocity, duration, channel=i)
                        if self.loop_recording:
                            self.loop.append((0, note, octave, waveform))
                    self.current_steps[i+2] = (self.current_steps[i+2] + 1) % self.synth_lengths[i]

        # Edit sequencer patterns
        if pyxel.btnp(pyxel.KEY_E):
            self.edit_mode = not self.edit_mode
            if self.edit_mode:
                self.edit_position = 0

        if pyxel.btnp(pyxel.KEY_T):
            self.edit_target = (self.edit_target + 1) % 4

        if self.edit_mode:
            current_pattern = self.drum_patterns[self.edit_target] if self.edit_target < 2 else self.synth_patterns[self.edit_target - 2]
            current_length = self.drum_lengths[self.edit_target] if self.edit_target < 2 else self.synth_lengths[self.edit_target - 2]
            
            if pyxel.btnp(pyxel.KEY_LEFT) and self.edit_position > 0:
                self.edit_position -= 1
            if pyxel.btnp(pyxel.KEY_RIGHT):
                self.edit_position = min(self.edit_position + 1, current_length)
            
            if pyxel.btnp(pyxel.KEY_SPACE):
                current_pattern[self.edit_position][0] = 1 - current_pattern[self.edit_position][0]
            
            if self.edit_target < 2:
                drum_keys = [pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4]
                for i, key in enumerate(drum_keys):
                    if pyxel.btnp(key):
                        current_pattern[self.edit_position][1] = i
                        current_pattern[self.edit_position][0] = 1
            else:
                synth_keys = [
                    pyxel.KEY_Z, pyxel.KEY_S, pyxel.KEY_X, pyxel.KEY_D, 
                    pyxel.KEY_C, pyxel.KEY_V, pyxel.KEY_G, pyxel.KEY_B, 
                    pyxel.KEY_H, pyxel.KEY_N, pyxel.KEY_J, pyxel.KEY_M
                ]
                for i, key in enumerate(synth_keys):
                    if pyxel.btnp(key):
                        current_pattern[self.edit_position][1] = i % 8
                        current_pattern[self.edit_position][2] = self.current_octave
                        current_pattern[self.edit_position][3] = self.current_waveform
                        current_pattern[self.edit_position][0] = 1
            
            if pyxel.btnp(pyxel.KEY_EQUALS):  # Use KEY_EQUAL for '+'
                if current_length < 32:
                    current_length += 1
                    current_pattern.append([0, 0, 100, 0.25] if self.edit_target < 2 else [0, 0, 0, 0, 100, 0.25])
            if pyxel.btnp(pyxel.KEY_MINUS):
                if current_length > 1:
                    current_length -= 1
                    current_pattern.pop()
            
            if pyxel.btnp(pyxel.KEY_BACKSPACE):
                self.edit_mode = False

    def draw(self):
        pyxel.cls(0)
        self.draw_frame()
        self.draw_instructions()
        self.draw_status()
        self.draw_volume_info()
        self.draw_sequencer()
        self.draw_logo()
        self.draw_edit_info()

    def draw_frame(self):
        # Draw a cyberpunk-style frame
        pyxel.rectb(0, 0, 360, 360, pyxel.COLOR_NEON_BLUE)
        pyxel.rect(1, 1, 358, 10, pyxel.COLOR_NEON_PINK)
        pyxel.text(5, 4, "NeoRetro Synth - Cyberpunk Edition", pyxel.COLOR_BLACK)

    def draw_instructions(self):
        pyxel.text(10, 20, "NeoRetro Synth Controls:", pyxel.COLOR_NEON_GREEN)
        instructions = [
            "Z-M: Synth (C2-C4)", "1-4: Drum sounds", "R: Toggle recording",
            "SPACE: Play/Stop", "C: Clear loop", "UP/DOWN: Octave",
            "LEFT/RIGHT: Sound length", "W: Change waveform", "Q: Quit",
            "F3: Save preset", "TAB: Toggle sequencer", "F4: Load preset",
            "F5: Toggle arpeggiator", "+/-: Change length", ".: Increase BPM",
            ",: Decrease BPM", "6/7: Drum volume", "8/9: Synth volume",
            "F1: Export MIDI", "F2: Export WAV"
        ]
        for i, instr in enumerate(instructions):
            pyxel.text(10 + (i // 10) * 180, 30 + (i % 10) * 10, instr, pyxel.COLOR_WHITE)

    def draw_status(self):
        pyxel.text(10, 140, f"NeoRetro Status:", pyxel.COLOR_NEON_BLUE)
        status = [
            f"Octave: {self.current_octave}", f"Sound Length: {self.sound_length}",
            f"Waveform: {self.waveforms[self.current_waveform]}", f"BPM: {self.bpm}",
            f"Recording: {'ON' if self.loop_recording else 'OFF'}", f"Playing: {'ON' if self.playing else 'OFF'}",
            f"Loop length: {len(self.loop)}", f"Sequencer: {'ON' if self.sequencer_playing else 'OFF'}",
            f"Arpeggiator: {'ON' if self.arpeggiator_on else 'OFF'}"
        ]
        for i, stat in enumerate(status):
            pyxel.text(10 + (i // 5) * 180, 150 + (i % 5) * 10, stat, pyxel.COLOR_YELLOW)

    def draw_volume_info(self):
        pyxel.text(10, 200, f"Drum Volume: {self.drum_volume}", pyxel.COLOR_WHITE)
        pyxel.text(120, 200, f"Synth Volume: {self.synth_volume}", pyxel.COLOR_WHITE)
        pyxel.text(230, 200, f"Sound Length: {self.sound_length}", pyxel.COLOR_WHITE)

    def draw_sequencer(self):
        for i in range(2):  # Draw drum sequencers
            drum_y = 220 + i * 30
            pyxel.text(10, drum_y, f"Drum {i+1} ({self.drum_lengths[i]}):", pyxel.COLOR_CYAN)
            for x, (is_active, sound_index, velocity, duration) in enumerate(self.drum_patterns[i][:self.drum_lengths[i]]):
                color = pyxel.COLOR_RED if is_active else pyxel.COLOR_DARK_BLUE
                pyxel.rect(x * 10 + 60, drum_y, 8, 8, color)
                if is_active:
                    pyxel.text(x * 10 + 62, drum_y + 2, self.drum_sounds[sound_index], pyxel.COLOR_WHITE)

        for i in range(2):  # Draw synth sequencers
            synth_y = 280 + i * 30
            pyxel.text(10, synth_y, f"Synth {i+1} ({self.synth_lengths[i]}):", pyxel.COLOR_CYAN)
            for x, (is_active, note, octave, waveform, velocity, duration) in enumerate(self.synth_patterns[i][:self.synth_lengths[i]]):
                color = pyxel.COLOR_RED if is_active else pyxel.COLOR_DARK_BLUE
                pyxel.rect(x * 10 + 60, synth_y, 8, 8, color)
                if is_active:
                    pyxel.text(x * 10 + 62, synth_y + 2, f"{self.synth_notes[note]}{self.waveforms[waveform][0]}", pyxel.COLOR_WHITE)

        # Highlight current steps and edit position
        if self.sequencer_playing:
            for i in range(2):
                pyxel.rect(self.current_steps[i] * 10 + 60, 220 + i * 30 + 10, 8, 2, pyxel.COLOR_WHITE)
                pyxel.rect(self.current_steps[i+2] * 10 + 60, 280 + i * 30 + 10, 8, 2, pyxel.COLOR_WHITE)

        if self.edit_mode:
            edit_x = self.edit_position * 10 + 60
            edit_y = 220 + (self.edit_target % 2) * 30 if self.edit_target < 2 else 280 + (self.edit_target - 2) * 30
            pyxel.rectb(edit_x, edit_y, 8, 8, pyxel.COLOR_YELLOW)

    def draw_logo(self):
        logo = [
            "  _   _             ____       _              ",
            " | \ | | ___  ___  |  _ \ ___ | |_ _ __ ___   ",
            " |  \| |/ _ \/ _ \ | |_) / _ \| __| '__/ _ \  ",
            " | |\  |  __/ (_) ||  _ < (_) | |_| | | (_) | ",
            " |_| \_|\___|\___/ |_| \_\___/ \__|_|  \___/  ",
            "  ____              _   _                     ",
            " / ___| _   _ _ __ | |_| |__                  ",
            " \___ \| | | | '_ \| __| '_ \                 ",
            "  ___) | |_| | | | | |_| | | |                ",
            " |____/ \__, |_| |_|\__|_| |_|                ",
            "        |___/                                 ",
            " v1.0                                         "
        ]
        for i, line in enumerate(logo):
            pyxel.text(170, 220 + i * 8, line, pyxel.COLOR_NEON_PINK)

        ascii_art = [
            "[ m a d e   b y   t c s e n p a i ]"
        ]

        for i, line in enumerate(ascii_art):
            pyxel.text(170, 340 + i * 8, line, pyxel.COLOR_NEON_YELLOW)
    
    def draw_edit_info(self):
        if self.edit_mode:
            if self.edit_target < 2:
                patterns = self.drum_patterns[self.edit_target]
                sounds = self.drum_sounds
                is_active, sound_index, velocity, duration = patterns[self.edit_position]
                state = f"{'ON' if is_active else 'OFF'} - {sounds[sound_index]} V:{velocity} D:{duration:.2f}"
            else:
                patterns = self.synth_patterns[self.edit_target - 2]
                sounds = self.synth_notes
                is_active, note, octave, waveform, velocity, duration = patterns[self.edit_position]
                state = f"{'ON' if is_active else 'OFF'} - {sounds[note]} O:{octave} W:{self.waveforms[waveform]} V:{velocity} D:{duration:.2f}"
            
            pyxel.text(10, 340, f"Editing: {'Drum' if self.edit_target < 2 else 'Synth'} {self.edit_target % 2 + 1} Step {self.edit_position+1} - {state}", pyxel.COLOR_WHITE)
            pyxel.text(10, 350, f"SPACE: Toggle, {'1-4: Set drum' if self.edit_target < 2 else 'Z-M: Set note'}, E: Edit mode, T: Switch tracks, BACKSPACE: Exit", pyxel.COLOR_WHITE)
        else:
            pyxel.text(10, 350, "E: Edit mode, T: Switch tracks", pyxel.COLOR_WHITE)

    def export_to_midi(self, filename="sequence.mid"):
        def write_var_length(value):
            result = bytearray()
            while value:
                result.insert(0, value & 0x7F | 0x80)
                value >>= 7
            if not result:
                result.append(0)
            result[-1] &= 0x7F
            return result

        def note_to_midi(note, octave):
            return note + (octave - 1) * 12 + 60

        with open(filename, "wb") as f:
            # Write MIDI header
            f.write(b'MThd')
            f.write(struct.pack('>IHHH', 6, 1, 2, 480))  # Chunk size, format, tracks, division

            # Write drum track
            f.write(b'MTrk')
            track_data = bytearray()
            track_data.extend(struct.pack('>I', 0))  # Delta time
            track_data.extend(b'\xFF\x51\x03' + struct.pack('>I', int(60000000 / self.bpm))[:3])  # Tempo

            for step, (is_active, sound_index, velocity, duration) in enumerate(self.drum_patterns[0][:self.drum_lengths[0]]):
                if is_active:
                    delta_time = write_var_length(step * 120)
                    note = 35 + sound_index  # Basic mapping for drum sounds
                    track_data.extend(delta_time + b'\x99' + bytes([note, velocity]))  # Note on
                    track_data.extend(write_var_length(int(duration * 480)) + b'\x89' + bytes([note, 0]))  # Note off

            track_data.extend(b'\x00\xFF\x2F\x00')  # End of track
            f.write(struct.pack('>I', len(track_data)))
            f.write(track_data)

            # Write synth track
            f.write(b'MTrk')
            track_data = bytearray()

            for step, (is_active, note, octave, waveform, velocity, duration) in enumerate(self.synth_patterns[0][:self.synth_lengths[0]]):
                if is_active:
                    delta_time = write_var_length(step * 120)
                    midi_note = note_to_midi(note, octave)
                    track_data.extend(delta_time + b'\x90' + bytes([midi_note, velocity]))  # Note on
                    track_data.extend(write_var_length(int(duration * 480)) + b'\x80' + bytes([midi_note, 0]))  # Note off

            track_data.extend(b'\x00\xFF\x2F\x00')  # End of track
            f.write(struct.pack('>I', len(track_data)))
            f.write(track_data)

        print(f"MIDI file exported as {filename}")
    
    def export_to_wav(self, filename="sequence.wav", duration=2):
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)

        audio = np.zeros_like(t)

        # Generate drum sounds
        for step, (is_active, sound_index, velocity, duration) in enumerate(self.drum_patterns[0][:self.drum_lengths[0]]):
            if is_active:
                freq = 100 + sound_index * 100  # Simple frequency mapping for drums
                audio += np.sin(2 * np.pi * freq * t) * np.exp(-t * 10) * (velocity / 100)

        # Generate synth sounds
        for step, (is_active, note, octave, waveform, velocity, duration) in enumerate(self.synth_patterns[0][:self.synth_lengths[0]]):
            if is_active:
                freq = 440 * 2**((note + (octave - 4) * 12) / 12)  # A4 = 440Hz
                if self.waveforms[waveform] == 'S':
                    wave = np.sign(np.sin(2 * np.pi * freq * t))
                elif self.waveforms[waveform] == 'T':
                    wave = np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1
                else:  # Default to sine wave
                    wave = np.sin(2 * np.pi * freq * t)
                envelope = np.exp(-t * 5)  # Simple envelope
                audio += wave * envelope * (velocity / 100)

        audio = np.int16(audio / np.max(np.abs(audio)) * 32767)
        wavfile.write(filename, sample_rate, audio)
        print(f"WAV file exported as {filename}")

    def save_preset(self, name):
        self.presets[name] = {
            'waveform': self.current_waveform,
            'drum_patterns': self.drum_patterns,
            'synth_patterns': self.synth_patterns
        }
        print(f"Preset '{name}' saved")

    def load_preset(self, name):
        if name in self.presets:
            preset = self.presets[name]
            self.current_waveform = preset['waveform']
            self.drum_patterns = preset['drum_patterns']
            self.synth_patterns = preset['synth_patterns']
            self.setup_sounds()
            print(f"Preset '{name}' loaded")
        else:
            print(f"Preset '{name}' not found")

    def toggle_arpeggiator(self):
        self.arpeggiator_on = not self.arpeggiator_on
        print(f"Arpeggiator {'ON' if self.arpeggiator_on else 'OFF'}")

    def apply_arpeggiator(self, note):
        if self.arpeggiator_on:
            return [note + offset for offset in self.arp_pattern]
        return [note]

    def handle_drum_input(self):
        drum_keys = [pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4]
        for i, key in enumerate(drum_keys):
            if pyxel.btnp(key):
                sound_index = 60 + i  # Drum sounds start at index 60
                pyxel.play(1, sound_index)
                print(f"Playing drum sound: {self.drum_sounds[i]}")
                if self.loop_recording:
                    self.loop.append((1, sound_index))

if __name__ == "__main__":
    NeoRetroSynth()