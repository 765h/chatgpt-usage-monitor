import unittest
from unittest.mock import MagicMock, call, patch

import tray


class RemainingRatioTest(unittest.TestCase):
    def test_boundaries(self):
        for used, remaining in ((0.0, 1.0), (0.5, 0.5), (0.8, 0.2), (1.0, 0.0)):
            with self.subTest(used=used):
                self.assertEqual(tray._remaining_ratio(used), remaining)

    def test_remaining_color_thresholds(self):
        for remaining, color in (
            (0.0, (240, 70, 60)),
            (0.19, (240, 70, 60)),
            (0.2, (255, 185, 50)),
            (0.49, (255, 185, 50)),
            (0.5, (80, 210, 100)),
            (1.0, (80, 210, 100)),
        ):
            with self.subTest(remaining=remaining):
                self.assertEqual(tray._remaining_color(remaining), color)

    def test_icon_shows_remaining_and_zero_as_cross(self):
        with patch.object(tray.ImageDraw, "Draw") as draw_factory, patch.object(
            tray, "_fit_font", return_value=object()
        ):
            tray.make_icon(1.0)
            self.assertEqual(draw_factory.return_value.text.call_args.args[1], "×")
            self.assertEqual(draw_factory.return_value.text.call_args.kwargs["fill"], (240, 70, 60))

            draw_factory.return_value.text.reset_mock()
            tray.make_icon(0.0)
            self.assertEqual(draw_factory.return_value.text.call_args.args[1], "100")
            self.assertEqual(draw_factory.return_value.text.call_args.kwargs["fill"], (80, 210, 100))
            draw_factory.return_value.rounded_rectangle.assert_not_called()

    def test_icon_shows_luna_badge_when_active(self):
        with patch.object(tray.ImageDraw, "Draw") as draw_factory, patch.object(
            tray, "_fit_font", return_value=object()
        ), patch.object(tray, "_get_font", return_value=object()):
            tray.make_icon(0.2, luna_active=True)
            draw_factory.return_value.ellipse.assert_called_once()

    def test_icon_uses_luna_remaining_as_main_number_when_active(self):
        with patch.object(tray.ImageDraw, "Draw") as draw_factory, patch.object(
            tray, "_fit_font", return_value=object()
        ), patch.object(tray, "_get_font", return_value=object()):
            tray.make_icon(1.0, luna_active=True, ratio_luna=0.23)

        main_number = next(
            call for call in draw_factory.return_value.text.call_args_list if call.args[1] == "77"
        )
        self.assertEqual(main_number.kwargs["fill"], tray.LUNA_ACTIVE_FG)
        draw_factory.return_value.rounded_rectangle.assert_called_once_with(
            (2, 2, 62, 62), radius=10, fill=tray.LUNA_ACTIVE_BG
        )
        draw_calls = draw_factory.return_value.text.call_args_list
        main_index = next(index for index, call in enumerate(draw_calls) if call.args[1] == "77")
        badge_index = next(index for index, call in enumerate(draw_calls) if call.args[1] == "L")
        self.assertLess(main_index, badge_index)

    def test_icon_keeps_luna_unknown_instead_of_using_session(self):
        with patch.object(tray.ImageDraw, "Draw") as draw_factory, patch.object(
            tray, "_fit_font", return_value=object()
        ), patch.object(tray, "_get_font", return_value=object()):
            tray.make_icon(0.2, luna_active=True)

        self.assertIn("—", [call.args[1] for call in draw_factory.return_value.text.call_args_list])
        draw_factory.return_value.rounded_rectangle.assert_not_called()

    def test_missing_usage_stays_unknown(self):
        self.assertEqual(tray.WAITING_TITLE, "ChatGPT 残量 — データ待機中")
        self.assertEqual(tray._format_remaining(None), "—")
        self.assertEqual(tray._make_tooltip(None, None, None), tray.WAITING_TITLE)
        self.assertNotIn("100%", tray._make_tooltip(None, None, None))

    def test_tooltip_converts_used_to_remaining(self):
        tooltip = tray._make_tooltip(0.8, 0.8, None)
        self.assertIn("Session 残量: 20%", tooltip)
        self.assertIn("Weekly 残量: 20%", tooltip)

    def test_tooltip_shows_luna_reserve_when_available(self):
        tooltip = tray._make_tooltip(0.8, 0.8, None, 0.13, None)
        self.assertIn("Luna reserve 残量: 87%", tooltip)

    def test_tooltip_shows_luna_reserve_without_session_data(self):
        tooltip = tray._make_tooltip(None, None, None, 0.23, None)
        self.assertIn("データ待機中", tooltip)
        self.assertIn("Luna reserve 残量: 77%", tooltip)

    def test_tooltip_marks_luna_reserve_active(self):
        tooltip = tray._make_tooltip(0.8, 0.8, None, 0.23, None, True)
        self.assertTrue(tooltip.startswith("現在利用中: Luna reserve 残量: 77%"))
        self.assertIn("Luna reserve 使用中", tooltip)

    def test_tooltip_keeps_luna_unknown_when_active(self):
        tooltip = tray._make_tooltip(0.2, 0.3, None, None, None, True)
        self.assertTrue(tooltip.startswith("現在利用中: Luna reserve 残量: —"))

    def test_popup_stays_compact_and_keeps_luna_detail(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1920
        win.winfo_screenheight.return_value = 1080
        win.winfo_reqwidth.return_value = 200
        win.winfo_reqheight.return_value = 300
        stats = {
            "utilization_5h": 0.2,
            "utilization_weekly": 0.3,
            "utilization_luna_reserve": 0.23,
            "luna_reserve_active": True,
        }
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()) as frame,
            patch.object(tray.tk, "Label", return_value=MagicMock()) as label,
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar"),
        ):
            tray.show_popup(stats)

        texts = [item.kwargs.get("text") for item in label.call_args_list]
        self.assertIn("Luna reserve", texts)
        self.assertIn("77%", texts)
        self.assertFalse(any(item.kwargs.get("bg") == tray.LUNA_ACTIVE_BG for item in frame.call_args_list))
        self.assertFalse(any(item.kwargs.get("bg") == tray.LUNA_ACTIVE_BG for item in label.call_args_list))

    def test_popup_schedules_periodic_refresh(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1920
        win.winfo_screenheight.return_value = 1080
        win.winfo_reqwidth.return_value = 200
        win.winfo_reqheight.return_value = 300
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()),
            patch.object(tray.tk, "Label", return_value=MagicMock()),
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar"),
        ):
            tray.show_popup({"utilization_5h": 0.2})

        refresh_calls = [
            item for item in win.after.call_args_list
            if item.args[0] == tray.POLL_INTERVAL * 1000
        ]
        self.assertEqual(len(refresh_calls), 1)
        self.assertTrue(callable(refresh_calls[0].args[1]))

    def test_popup_refresh_redraws_with_latest_stats(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1920
        win.winfo_screenheight.return_value = 1080
        win.winfo_reqwidth.return_value = 200
        win.winfo_reqheight.return_value = 300
        latest = {"utilization_5h": 0.8, "utilization_weekly": 0.4}
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()),
            patch.object(tray.tk, "Label", return_value=MagicMock()) as label,
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar"),
            patch.object(tray.codex_usage, "get_last_data", return_value=latest) as get_data,
        ):
            tray.show_popup({"utilization_5h": 0.2, "utilization_weekly": 0.3})
            refresh = next(
                item.args[1] for item in win.after.call_args_list
                if item.args[0] == tray.POLL_INTERVAL * 1000
            )
            refresh()

        get_data.assert_called_once_with()
        self.assertIn("20%", [item.kwargs.get("text") for item in label.call_args_list])
        self.assertGreaterEqual(win.geometry.call_count, 2)
        refresh_calls = [
            item for item in win.after.call_args_list
            if item.args[0] == tray.POLL_INTERVAL * 1000
        ]
        self.assertEqual(len(refresh_calls), 2)

    def test_popup_refresh_keeps_resized_window_inside_screen(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1366
        win.winfo_screenheight.return_value = 768
        win.winfo_reqwidth.side_effect = [200, 200]
        win.winfo_reqheight.side_effect = [300, 700]
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()),
            patch.object(tray.tk, "Label", return_value=MagicMock()),
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar"),
            patch.object(tray.codex_usage, "get_last_data", return_value={"utilization_5h": 0.2}),
        ):
            tray.show_popup({"utilization_5h": 0.2})
            refresh = next(
                item.args[1] for item in win.after.call_args_list
                if item.args[0] == tray.POLL_INTERVAL * 1000
            )
            refresh()

        self.assertEqual(win.geometry.call_args.args[0], "200x700+1150+12")

    def test_popup_keeps_unknown_active_luna_row(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1920
        win.winfo_screenheight.return_value = 1080
        win.winfo_reqwidth.return_value = 200
        win.winfo_reqheight.return_value = 300
        stats = {
            "utilization_5h": 0.2,
            "utilization_luna_reserve": None,
            "luna_reserve_active": True,
        }
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()),
            patch.object(tray.tk, "Label", return_value=MagicMock()) as label,
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar") as usage_bar,
        ):
            tray.show_popup(stats)

        texts = [item.kwargs.get("text") for item in label.call_args_list]
        self.assertIn("Luna reserve", texts)
        self.assertIn("—", texts)
        usage_bar.assert_called_once()

    def test_tray_applies_initial_stats_before_run(self):
        icon = MagicMock()
        stats = {
            "utilization_5h": 0.2,
            "utilization_weekly": 0.3,
            "luna_reserve_active": False,
        }
        with (
            patch.object(tray.pystray, "Icon", return_value=icon),
            patch.object(tray.codex_usage, "get_last_data", return_value=stats) as get_data,
            patch.object(tray.threading, "Thread") as thread,
            patch.object(tray, "make_icon", return_value=MagicMock()) as make_icon,
        ):
            tray.run_tray()

        get_data.assert_called_once_with()
        self.assertEqual(make_icon.call_args_list[-1].args, (0.2, False, None))
        icon.run.assert_called_once_with()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()

    def test_tray_poll_continues_after_update_exception(self):
        icon = MagicMock()
        initial = {"utilization_5h": 0.2, "utilization_weekly": 0.3}
        latest = {"utilization_5h": 0.8, "utilization_weekly": 0.4}
        with (
            patch.object(tray.pystray, "Icon", return_value=icon),
            patch.object(
                tray.codex_usage,
                "get_last_data",
                side_effect=[initial, RuntimeError("temporary failure"), latest],
            ) as get_data,
            patch.object(tray.threading, "Thread") as thread,
            patch.object(tray, "make_icon", return_value=MagicMock()) as make_icon,
            patch.object(tray.time, "sleep", side_effect=[None, None, KeyboardInterrupt]),
            patch.object(tray.LOGGER, "exception") as log,
        ):
            tray.run_tray()
            poll_loop = thread.call_args.kwargs["target"]
            with self.assertRaises(KeyboardInterrupt):
                poll_loop()

        self.assertEqual(get_data.call_count, 3)
        log.assert_called_once_with("Tray usage update failed")
        self.assertEqual(make_icon.call_args_list[-1].args, (0.8, False, None))

    def test_popup_missing_usage_has_no_bars(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1920
        win.winfo_screenheight.return_value = 1080
        win.winfo_reqwidth.return_value = 200
        win.winfo_reqheight.return_value = 300
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()),
            patch.object(tray.tk, "Label", return_value=MagicMock()) as label,
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar") as usage_bar,
        ):
            tray.show_popup({})

        usage_bar.assert_not_called()
        self.assertIn("—", [item.kwargs.get("text") for item in label.call_args_list])

    def test_popup_shows_luna_reserve_when_available(self):
        win = MagicMock()
        win.winfo_screenwidth.return_value = 1920
        win.winfo_screenheight.return_value = 1080
        win.winfo_reqwidth.return_value = 200
        win.winfo_reqheight.return_value = 300
        with (
            patch.object(tray.tk, "Tk", return_value=win),
            patch.object(tray.tk, "Frame", return_value=MagicMock()),
            patch.object(tray.tk, "Label", return_value=MagicMock()) as label,
            patch.object(tray.tk, "Button", return_value=MagicMock()),
            patch.object(tray, "_usage_bar"),
        ):
            for used_ratio, expected_remaining in ((0.13, "87%"), (0.41, "59%")):
                tray.show_popup({
                    "utilization_5h": 0.2,
                    "utilization_weekly": 0.3,
                    "utilization_luna_reserve": used_ratio,
                })

                texts = [item.kwargs.get("text") for item in label.call_args_list]
                self.assertIn("Luna reserve", texts)
                self.assertIn(expected_remaining, texts)
                label.reset_mock()

    def test_usage_bar_uses_remaining_width_and_color(self):
        frame = MagicMock()
        canvas = MagicMock()
        canvas.winfo_width.return_value = 100
        with (
            patch.object(tray.tk, "Frame", return_value=frame),
            patch.object(tray.tk, "Canvas", return_value=canvas),
        ):
            tray._usage_bar(MagicMock(), 0.2)
            draw = canvas.bind.call_args.args[1]
            draw()
            self.assertEqual(
                canvas.create_rectangle.call_args_list,
                [
                    call(0, 0, 100, 6, fill=tray.BAR_BG, outline=""),
                    call(0, 0, 20, 6, fill="#ffb932", outline=""),
                ],
            )

            canvas.reset_mock()
            canvas.winfo_width.return_value = 100
            tray._usage_bar(MagicMock(), 0.0)
            draw = canvas.bind.call_args.args[1]
            draw()
            self.assertEqual(
                canvas.create_rectangle.call_args_list,
                [call(0, 0, 100, 6, fill=tray.BAR_BG, outline="")],
            )


if __name__ == "__main__":
    unittest.main()
