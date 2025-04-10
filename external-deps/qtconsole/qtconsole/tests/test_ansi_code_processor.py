# Standard library imports
import unittest

# Local imports
from qtconsole.ansi_code_processor import AnsiCodeProcessor, QtAnsiCodeProcessor


class TestAnsiCodeProcessor(unittest.TestCase):

    def setUp(self):
        self.processor = AnsiCodeProcessor()
        self.qt_processor = QtAnsiCodeProcessor()

    def test_clear(self):
        """ Do control sequences for clearing the console work?
        """
        string = '\x1b[2J\x1b[K'
        i = -1
        for i, substring in enumerate(self.processor.split_string(string)):
            if i == 0:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'erase')
                self.assertEqual(action.area, 'screen')
                self.assertEqual(action.erase_to, 'all')
            elif i == 1:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'erase')
                self.assertEqual(action.area, 'line')
                self.assertEqual(action.erase_to, 'end')
            else:
                self.fail('Too many substrings.')
        self.assertEqual(i, 1, 'Too few substrings.')
    
    #test_erase_in_line() is in test_00_console_widget.py, because it needs the console

    def test_colors(self):
        """ Do basic controls sequences for colors work?
        """
        string = 'first\x1b[34mblue\x1b[0mlast\033[33mYellow'
        i = -1
        for i, substring in enumerate(self.processor.split_string(string)):
            if i == 0:
                self.assertEqual(substring, 'first')
                self.assertEqual(self.processor.foreground_color, None)
            elif i == 1:
                self.assertEqual(substring, 'blue')
                self.assertEqual(self.processor.foreground_color, 4)
            elif i == 2:
                self.assertEqual(substring, 'last')
                self.assertEqual(self.processor.foreground_color, None)
            elif i == 3:
                foreground_color = self.processor.foreground_color
                self.assertEqual(substring, 'Yellow')
                self.assertEqual(foreground_color, 3)
                self.assertEqual(self.qt_processor.get_color(foreground_color).name(), '#ffd700')
            else:
                self.fail('Too many substrings.')
        self.assertEqual(i, 3, 'Too few substrings.')

    def test_colors_xterm(self):
        """ Do xterm-specific control sequences for colors work?
        """
        string = '\x1b]4;20;rgb:ff/ff/ff\x1b' \
            '\x1b]4;25;rgbi:1.0/1.0/1.0\x1b'
        substrings = list(self.processor.split_string(string))
        desired = { 20 : (255, 255, 255),
                    25 : (255, 255, 255) }
        self.assertEqual(self.processor.color_map, desired)

        string = '\x1b[38;5;20m\x1b[48;5;25m'
        substrings = list(self.processor.split_string(string))
        self.assertEqual(self.processor.foreground_color, 20)
        self.assertEqual(self.processor.background_color, 25)

    def test_true_color(self):
        """Do 24bit True Color control sequences?
        """
        string = '\x1b[38;2;255;100;0m\x1b[48;2;100;100;100m'
        substrings = list(self.processor.split_string(string))
        self.assertEqual(self.processor.foreground_color, [255, 100, 0])
        self.assertEqual(self.processor.background_color, [100, 100, 100])

    def test_scroll(self):
        """ Do control sequences for scrolling the buffer work?
        """
        string = '\x1b[5S\x1b[T'
        i = -1
        for i, substring in enumerate(self.processor.split_string(string)):
            if i == 0:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'scroll')
                self.assertEqual(action.dir, 'up')
                self.assertEqual(action.unit, 'line')
                self.assertEqual(action.count, 5)
            elif i == 1:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'scroll')
                self.assertEqual(action.dir, 'down')
                self.assertEqual(action.unit, 'line')
                self.assertEqual(action.count, 1)
            else:
                self.fail('Too many substrings.')
        self.assertEqual(i, 1, 'Too few substrings.')

    def test_formfeed(self):
        """ Are formfeed characters processed correctly?
        """
        string = '\f' # form feed
        self.assertEqual(list(self.processor.split_string(string)), [''])
        self.assertEqual(len(self.processor.actions), 1)
        action = self.processor.actions[0]
        self.assertEqual(action.action, 'scroll')
        self.assertEqual(action.dir, 'down')
        self.assertEqual(action.unit, 'page')
        self.assertEqual(action.count, 1)

    def test_carriage_return(self):
        """ Are carriage return characters processed correctly?
        """
        string = 'foo\rbar' # carriage return
        splits = []
        actions = []
        for split in self.processor.split_string(string):
            splits.append(split)
            actions.append([action.action for action in self.processor.actions])
        self.assertEqual(splits, ['foo', None, 'bar'])
        self.assertEqual(actions, [[], ['carriage-return'], []])

    def test_carriage_return_newline(self):
        """transform CRLF to LF"""
        string = 'foo\rbar\r\ncat\r\n\n' # carriage return and newline
        # only one CR action should occur, and '\r\n' should transform to '\n'
        splits = []
        actions = []
        for split in self.processor.split_string(string):
            splits.append(split)
            actions.append([action.action for action in self.processor.actions])
        self.assertEqual(splits, ['foo', None, 'bar', None, 'cat', None, None])
        self.assertEqual(actions, [[], ['carriage-return'], [], ['newline'], [], ['newline'], ['newline']])

    def test_beep(self):
        """ Are beep characters processed correctly?
        """
        string = 'foo\abar' # bell
        splits = []
        actions = []
        for split in self.processor.split_string(string):
            splits.append(split)
            actions.append([action.action for action in self.processor.actions])
        self.assertEqual(splits, ['foo', None, 'bar'])
        self.assertEqual(actions, [[], ['beep'], []])

    def test_backspace(self):
        """ Are backspace characters processed correctly?
        """
        string = 'foo\bbar' # backspace
        splits = []
        actions = []
        for split in self.processor.split_string(string):
            splits.append(split)
            actions.append([action.action for action in self.processor.actions])
        self.assertEqual(splits, ['foo', None, 'bar'])
        self.assertEqual(actions, [[], ['backspace'], []])

    def test_combined(self):
        """ Are CR and BS characters processed correctly in combination?

        BS is treated as a change in print position, rather than a
        backwards character deletion.  Therefore a BS at EOL is
        effectively ignored.
        """
        string = 'abc\rdef\b' # CR and backspace
        splits = []
        actions = []
        for split in self.processor.split_string(string):
            splits.append(split)
            actions.append([action.action for action in self.processor.actions])
        self.assertEqual(splits, ['abc', None, 'def', None])
        self.assertEqual(actions, [[], ['carriage-return'], [], ['backspace']])

    def test_move_cursor_up(self):
        """Are the ANSI commands for the cursor movement actions
        (movement up and to the beginning of the line) processed correctly?
        """
        # This line moves the cursor up once, then moves it up five more lines.
        # Next, it moves the cursor to the beginning of the previous line, and
        # finally moves it to the beginning of the fifth line above the current 
        # position
        string = '\x1b[A\x1b[5A\x1b[F\x1b[5F'
        i = -1
        for i, substring in enumerate(self.processor.split_string(string)):
            if i == 0:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'move')
                self.assertEqual(action.dir, 'up')
                self.assertEqual(action.unit, 'line')
                self.assertEqual(action.count, 1)
            elif i == 1:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'move')
                self.assertEqual(action.dir, 'up')
                self.assertEqual(action.unit, 'line')
                self.assertEqual(action.count, 5)
            elif i == 2:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'move')
                self.assertEqual(action.dir, 'leftup')
                self.assertEqual(action.unit, 'line')
                self.assertEqual(action.count, 1)
            elif i == 3:
                self.assertEqual(len(self.processor.actions), 1)
                action = self.processor.actions[0]
                self.assertEqual(action.action, 'move')
                self.assertEqual(action.dir, 'leftup')
                self.assertEqual(action.unit, 'line')
                self.assertEqual(action.count, 5)
            else:
                self.fail('Too many substrings.')
        self.assertEqual(i, 3, 'Too few substrings.')


if __name__ == '__main__':
    unittest.main()
