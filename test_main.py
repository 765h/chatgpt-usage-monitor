import subprocess
import unittest
from unittest.mock import MagicMock, patch

import main


class InstallTest(unittest.TestCase):
    def test_failed_task_registration_does_not_create_marker(self):
        install_dir = MagicMock()
        marker = MagicMock()
        with (
            patch.object(main, "INSTALL_DIR", install_dir),
            patch.object(main, "MARKER", marker),
            patch.object(main.shutil, "copy2"),
            patch.object(main.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "schtasks")),
            patch.object(main.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                main._do_install()

        marker.write_text.assert_not_called()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
