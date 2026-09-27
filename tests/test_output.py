"""Human output stays readable without terminal color support."""

import io
import unittest
from unittest.mock import patch

from etchlib.output import present, write_output


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


class OutputTests(unittest.TestCase):
    def test_colors_status_labels_without_changing_the_message(self) -> None:
        text = "  demo:action[0]: CHANGE — link config\nWarning: review this"
        colored = present(text, True)
        self.assertIn("\x1b[36mCHANGE\x1b[0m", colored)
        self.assertIn("\x1b[33mWarning\x1b[0m", colored)
        self.assertEqual(present(text, False), text)

    def test_non_terminal_and_no_color_remain_plain(self) -> None:
        text = "CHANGED demo:action[0]: linked"
        pipe = io.StringIO()
        write_output(text, pipe)
        self.assertEqual(pipe.getvalue(), text + "\n")

        terminal = Terminal()
        with patch.dict("os.environ", {"NO_COLOR": "", "TERM": "xterm"}):
            write_output(text, terminal)
        self.assertEqual(terminal.getvalue(), text + "\n")


if __name__ == "__main__":
    unittest.main()
