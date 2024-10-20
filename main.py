"""
To run, install Haiku-PyAPI, trimgmi and gusmobile
pip install trimgmi git+https://git.sr.ht/~rwa/gusmobile
"""

import gusmobile
from trimgmi import *
from urllib.parse import urljoin, uses_relative, uses_netloc, uses_params
from Be import *
import Be
from time import sleep
import threading

GO_BUTTON_MSG = BMessage(int32(b"GBMs"))
BACK_BUTTON_MSG = BMessage(int32(b"BBMs"))
HOME_BUTTON_MSG = BMessage(int32(b"HBMs"))
START_MSG = BMessage(int32(b"STMs"))
PAGE_FETCHED_MSG = BMessage(int32(b"GtPg"))
for uses in (uses_relative, uses_netloc, uses_params):
    uses.append('gemini')

def tlen(string):
    return len(string.encode())


class BrowserView(BTextView):
    def MouseDown(self, where):
        offset=self.OffsetAt(where)
        for link in self.window.links:
            if offset in link[0]:
                url=urljoin(self.window.history[-1],link[1])
                self.window.load_page(url)
                


class MainWindow(BWindow):
    def __init__(self):
        BWindow.__init__(
            self,
            BRect(100, 100, 800, 500),
            "Bemini",
            B_TITLED_WINDOW,
            B_QUIT_ON_WINDOW_CLOSE,
        )
        self.events.update(
            {
                GO_BUTTON_MSG.what: self.go,
                BACK_BUTTON_MSG.what: self.go_back,
                START_MSG.what: self.start,
                PAGE_FETCHED_MSG.what: self.display_page,
            }
        )

        self.history = []
        self.links=[]
        self.current_url=""
        self.current_response=None
        self.lock = threading.Lock()

        # KLUDGE1: Get around a double free
        self.alerts = []

        self.back_button = BButton("back_button", "Back", BMessage(BACK_BUTTON_MSG))

        self.go_button = BButton("go_button", "Go!", BMessage(GO_BUTTON_MSG))

        self.url_input = BTextControl("", "gemini://", BMessage(GO_BUTTON_MSG))

        self.setup_fonts()

        self.content = BrowserView("content")
        self.content.window=self
        self.content_scroll = BScrollView(
            "content_scroll", self.content, 0, False, True, B_NO_BORDER
        )
        self.content.SetHighUIColor(B_DOCUMENT_TEXT_COLOR)
        self.content.SetLowUIColor(B_DOCUMENT_BACKGROUND_COLOR)

        self.home_page()

        self.layout = BGroupLayout(B_VERTICAL, 5)
        self.SetLayout(self.layout)
        self.top_bar_layout = BGroupLayout(B_HORIZONTAL)
        self.layout.AddItem(self.top_bar_layout, 1)
        self.top_bar_layout.AddView(self.back_button)
        self.top_bar_layout.AddView(self.url_input)
        self.top_bar_layout.AddView(self.go_button)
        self.layout.AddView(self.content_scroll, 20)
        self.layout.SetInsets(3)

        self.PostMessage(START_MSG)

    def go_back(self, msg):
        if len(self.history) > 1:
            self.history.pop()
            self.load_page(self.history[-1])
            self.url_input.SetText(self.history[-1])
        else:
            self.home_page()
            self.url_input.SetText("")

    def home_page(self):
        gemtext = "# Bemini\nWelcome to Bemini, the Gemini browser for Haiku!\nWritten in Python with Haiku-PyAPI."
        text_runs, text, links = self.parse_page(gemtext)
        run_array = BTextView.AllocRunArray(len(text_runs))
        run_array.runs = text_runs
        self.content.SetStylable(True)
        self.content.SetText(text, run_array)

    def start(self, msg):
        self.content.MakeEditable(False)

    def go(self, msg):
        url = self.url_input.Text()
        self.load_page(url)
    def load_page(self,url):
        threading.Thread(target=self.fetch_page,args=(url,), daemon=True).start()
    def fetch_page(self,url):
        print(f"Fetching {url}... ", end="")
        response = gusmobile.fetch(url)
        with self.lock:
            self.current_url=url
            self.current_response=response
        self.PostMessage(PAGE_FETCHED_MSG)
    def display_page(self, msg):
        with self.lock:
            url=self.current_url
            response=self.current_response
        if response:
            print(response.status)
            if response.status.startswith("2"):
                text_runs, text, links = self.parse_page(response.content)
                run_array = BTextView.AllocRunArray(len(text_runs))
                run_array.runs = text_runs
                self.content.SetText(text, run_array)
                self.url_input.SetText(url)
                self.history.append(url)
                self.links = links
                print(links)
            else:
                alert = BAlert(
                    "Error",
                    f"Gemini error code {response.status}",
                    "OK",
                    None,
                    None,
                    B_WIDTH_AS_USUAL,
                    B_WARNING_ALERT,
                )
                alert.Go()
                # KLUDGE1
                self.alerts.append(alert)
                # ------------------------
        else:
            alert = BAlert(
                "Error",
                f"Failed to fetch page",
                "OK",
                None,
                None,
                B_WIDTH_AS_USUAL,
                B_WARNING_ALERT,
            )
            alert.Go()
            # KLUDGE1
            self.alerts.append(alert)

    def setup_fonts(self):
        heading_base_size = be_bold_font.Size()
        self.heading1_font = BFont(be_bold_font)
        self.heading1_font.SetSize(heading_base_size + 15)
        self.heading2_font = BFont(be_bold_font)
        self.heading2_font.SetSize(heading_base_size + 10)
        self.heading3_font = BFont(be_bold_font)
        self.heading3_font.SetSize(heading_base_size + 5)
        self.link_font = BFont(be_bold_font)
        self.link_font.SetFace(B_UNDERSCORE_FACE)
        self.mono_font = BFont(be_fixed_font)
        self.regular_font = BFont(be_plain_font)

    def parse_page(self, text):
        text_runs = []
        links = []
        final_text = ""
        index = 0
        document = Document()
        for line in text.splitlines():
            document.append(line)
        for line in document.emit_line_objects():
            run = text_run()
            run.offset = index
            run.color = ui_color(B_DOCUMENT_TEXT_COLOR)
            if line.type == LineType.BLANK:
                t = "\n"
                index += tlen(t)
                final_text += t
                run.font = self.regular_font
            elif line.type == LineType.REGULAR:
                t = line.text + "\n"
                index += tlen(t)
                final_text += t
                run.font = self.regular_font
            elif line.type == LineType.LINK:
                t = ""
                if line.text == "":
                    t = f"    {line.extra}\n"
                else:
                    t = f"    {line.text}\n"
                index += tlen(t)
                final_text += t
                links.append((range(tlen(final_text) - (tlen(t) - 4), tlen(final_text) - 1),line.extra))
                run.font = self.link_font
                run.color.set_to(0, 120, 140)
            elif line.type == LineType.HEADING1:
                t = line.text + "\n"
                index += tlen(t)
                final_text += t
                run.font = self.heading1_font
            elif line.type == LineType.HEADING2:
                t = line.text + "\n"
                index += tlen(t)
                final_text += t
                run.font = self.heading2_font
            elif line.type == LineType.HEADING3:
                t = line.text + "\n"
                index += tlen(t)
                final_text += t
                run.font = self.heading3_font
            elif line.type == LineType.LIST_ITEM:
                t = "◦ " + line.text + "\n"
                index += tlen(t) + 2
                final_text += t
                run.font = self.regular_font
            elif line.type == LineType.QUOTE:
                t = "▎ " + line.text + "\n"
                index += tlen(t) + 2
                final_text += t
                run.font = self.regular_font
                if ui_color(B_DOCUMENT_TEXT_COLOR).IsDark():
                    run.color.set_to(60,60,60)
                else:
                    run.color.set_to(195,195,195)
            elif line.type == LineType.PREFORMAT_LINE:
                t = line.text + "\n"
                index += tlen(t)
                final_text += t
                run.font = self.mono_font
            text_runs.append(run)
        return text_runs, final_text, links


class Bemini(BApplication):
    def __init__(self):
        BApplication.__init__(self, "application/x-bemini")
        self.window = MainWindow()
        self.window.Show()

    def QuitRequested(self):
        return True


def main():
    app = Bemini()
    app.Run()
    # KLUDGE2: Another kludge to get around a race condition somewhere
    sleep(0.1)


if __name__ == "__main__":
    main()
