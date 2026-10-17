import threading

import phonenumbers
import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from utils import lookup_domain, lookup_ip, lookup_phone


class InfoGMobileApp(App):
    title = 'InfoG'

    def build(self):
        root = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(12),
        )
        root.add_widget(Label(
            text='InfoG',
            font_size='30sp',
            bold=True,
            size_hint_y=None,
            height=dp(48),
            color=(0.08, 0.22, 0.20, 1),
        ))
        root.add_widget(Label(
            text='Network and number lookups',
            size_hint_y=None,
            height=dp(28),
            color=(0.30, 0.35, 0.34, 1),
        ))

        self.lookup_mode = Spinner(
            text='Domain IP address',
            values=(
                'Domain IP address',
                'IP address details',
                'Phone number details',
            ),
            size_hint_y=None,
            height=dp(52),
            background_color=(0.88, 0.94, 0.91, 1),
            color=(0.08, 0.22, 0.20, 1),
        )
        root.add_widget(self.lookup_mode)

        self.lookup_input = TextInput(
            hint_text='Enter a domain, IP address, or phone number with country code',
            multiline=False,
            size_hint_y=None,
            height=dp(58),
            padding=(dp(12), dp(18)),
        )
        root.add_widget(self.lookup_input)

        self.lookup_button = Button(
            text='Look up',
            size_hint_y=None,
            height=dp(52),
            background_normal='',
            background_color=(0.10, 0.43, 0.35, 1),
            color=(1, 1, 1, 1),
        )
        self.lookup_button.bind(on_release=self.start_lookup)
        root.add_widget(self.lookup_button)

        self.results = TextInput(
            text='Results will appear here.',
            readonly=True,
            multiline=True,
            size_hint_y=1,
            padding=dp(12),
            background_color=(0.96, 0.97, 0.95, 1),
            foreground_color=(0.10, 0.16, 0.15, 1),
        )
        root.add_widget(self.results)
        return root

    def start_lookup(self, _button):
        value = self.lookup_input.text.strip()
        if not value:
            self.results.text = 'Enter a value to look up.'
            return

        self.lookup_button.disabled = True
        self.lookup_button.text = 'Looking up...'
        self.results.text = ''
        threading.Thread(
            target=self._perform_lookup,
            args=(self.lookup_mode.text, value),
            daemon=True,
        ).start()

    def _perform_lookup(self, mode, value):
        try:
            if mode == 'Domain IP address':
                result = f'{value}\n\nIP address: {lookup_domain(value)}'
            elif mode == 'IP address details':
                result = '\n'.join(
                    f'{key}: {value}'
                    for key, value in lookup_ip(value).items()
                )
            else:
                region, carrier = lookup_phone(value)
                result = f'Region: {region}\nService provider: {carrier}'
        except (OSError, ValueError, phonenumbers.NumberParseException,
                requests.RequestException) as error:
            result = f'Lookup failed: {error}'
        except Exception as error:
            result = f'Lookup failed: {error}'

        Clock.schedule_once(lambda _dt: self._show_result(result))

    def _show_result(self, result):
        self.results.text = result
        self.lookup_button.disabled = False
        self.lookup_button.text = 'Look up'


if __name__ == '__main__':
    InfoGMobileApp().run()