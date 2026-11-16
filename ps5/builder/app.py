"""Longshot PS5 Builder, the window: choose your game file, build the PS5 title folder, copy it to the console.

    python app.py

PyQt6. The build itself is ps5/builder/pipeline.py, run as a process of its own with this Python; this window shows its
steps and its log, and can send the finished folder to a console over FTP. Nothing is sent anywhere else.
"""
import ftplib
import os
import sys

from PyQt6.QtCore import QProcess, QSettings, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QTextCursor
from PyQt6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.environ.get("LONGSHOT_PS5_PIPELINE", os.path.join(HERE, "pipeline.py"))
STEPS = ["Reading the game's program", "Translating it to C", "Compiling for the console", "Linking", "Making the title folder"]
ABOUT = {
    1: "A few seconds.",
    2: "5 to 10 minutes. Uses about 6 GB of memory.",
    3: "The long step: 30 to 60 minutes on a 6-core PC.",
    4: "Under a minute.",
    5: "A few seconds.",
}


class Sender(QThread):
    """the title folder to /data/homebrew/<title id> on the console, over FTP"""
    progress = pyqtSignal(int, int)
    said = pyqtSignal(str)
    ended = pyqtSignal(str)   # ("" when it worked)

    def __init__(self, folder, host, port):
        super().__init__()
        self.folder, self.host, self.port = folder, host, port

    def run(self):
        try:
            title = os.path.basename(self.folder.rstrip("/\\"))
            files = []
            for base, _, names in os.walk(self.folder):
                for n in names:
                    p = os.path.join(base, n)
                    files.append((p, os.path.relpath(p, self.folder).replace(os.sep, "/")))
            # (eboot.bin and param.json last: the console lists the title once they are there)
            files.sort(key=lambda f: (f[1] in ("eboot.bin", "sce_sys/param.json"), f[1]))
            total = sum(os.path.getsize(p) for p, _ in files)
            sent = 0
            ftp = ftplib.FTP()
            ftp.connect(self.host, self.port, timeout=30)
            ftp.login()
            ftp.voidcmd("TYPE I")
            root = "/data/homebrew/" + title

            def mkdirs(path):
                at = ""
                for part in path.strip("/").split("/"):
                    at += "/" + part
                    try:
                        ftp.mkd(at)
                    except ftplib.all_errors:
                        pass
            mkdirs(root)
            for path, rel in files:
                if "/" in rel:
                    mkdirs(root + "/" + rel.rsplit("/", 1)[0])
                self.said.emit("sending " + rel)
                with open(path, "rb") as f:
                    def block(b):
                        nonlocal sent
                        sent += len(b)
                        self.progress.emit(sent >> 10, max(1, total >> 10))
                    ftp.storbinary("STOR " + root + "/" + rel, f, blocksize=1 << 20, callback=block)
            try:
                ftp.quit()
            except ftplib.all_errors:
                pass
            self.ended.emit("")
        except Exception as e:   # (shown to the player as it is)
            self.ended.emit("%s: %s" % (type(e).__name__, e))


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Longshot PS5 Builder")
        self.settings = QSettings("PS5_Longshot", "Builder")
        self.proc = None
        self.sender = None
        self.built = ""
        self.stopping = False
        self.pending = ""

        head = QLabel("Longshot PS5 Builder")
        f = QFont(self.font())
        f.setPointSize(f.pointSize() + 6)
        f.setBold(True)
        head.setFont(f)
        sub = QLabel("Builds the PlayStation 5 title folder from your own copy of the game. The build happens on this "
                     "computer; the folder it makes is yours alone and must not be shared.")
        sub.setWordWrap(True)

        self.game = QLineEdit(self.settings.value("game", ""))
        self.game.setPlaceholderText("Your game file (.nup)")
        game_pick = QPushButton("Choose…")
        game_pick.clicked.connect(self.pick_game)
        self.out = QLineEdit(self.settings.value("out", os.path.join(os.path.expanduser("~"), "Longshot-PS5")))
        out_pick = QPushButton("Choose…")
        out_pick.clicked.connect(self.pick_out)
        form = QFormLayout()
        form.addRow("Game file", self.row(self.game, game_pick))
        form.addRow("Build into", self.row(self.out, out_pick))
        self.jobs = QSpinBox()
        self.jobs.setRange(0, 64)
        self.jobs.setSpecialValueText("Automatic")
        self.jobs.setValue(int(self.settings.value("jobs", 0)))
        self.jobs.setToolTip("Files compiled at once. Automatic: by this computer's cores and free memory "
                             "(each takes up to 1.4 GB). Lower it if the build is stopped for want of memory.")
        form.addRow("Compile at once", self.jobs)

        self.steps = []
        steps_box = QVBoxLayout()
        steps_box.setSpacing(2)
        for i, name in enumerate(STEPS, 1):
            l = QLabel()
            l.setTextFormat(Qt.TextFormat.RichText)
            self.steps.append(l)
            steps_box.addWidget(l)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.status = QLabel("Choose your game file, then Build.")
        self.status.setWordWrap(True)

        self.go = QPushButton("Build")
        self.go.setDefault(True)
        self.go.clicked.connect(self.start_or_stop)
        self.open = QPushButton("Open folder")
        self.open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.built)))
        self.open.setEnabled(False)
        self.details = QCheckBox("Show details")
        self.details.toggled.connect(lambda on: self.log.setVisible(on))
        buttons = QHBoxLayout()
        buttons.addWidget(self.details)
        buttons.addStretch(1)
        buttons.addWidget(self.open)
        buttons.addWidget(self.go)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.log.setFont(mono)
        self.log.setVisible(False)
        self.log.setMinimumHeight(180)

        # ---- the console ----
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        self.ps5 = QLineEdit(self.settings.value("ps5", ""))
        self.ps5.setPlaceholderText("Console's address, for example 192.168.0.190")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(self.settings.value("port", 2121)))
        self.send = QPushButton("Send to PS5")
        self.send.setEnabled(False)
        self.send.clicked.connect(self.start_send)
        send_row = QHBoxLayout()
        send_row.addWidget(self.ps5, 1)
        send_row.addWidget(QLabel("FTP port"))
        send_row.addWidget(self.port)
        send_row.addWidget(self.send)
        self.send_note = QLabel("When the build is done: copy the title folder to <b>/data/homebrew</b> on the console yourself, "
                                "or send it from here with the console's FTP server running. Your game file goes to "
                                "<b>/data/eglantineps5/roms</b> on the console.")
        self.send_note.setWordWrap(True)
        self.send_note.setTextFormat(Qt.TextFormat.RichText)

        box = QVBoxLayout(self)
        box.addWidget(head)
        box.addWidget(sub)
        box.addLayout(form)
        box.addLayout(steps_box)
        box.addWidget(self.bar)
        box.addWidget(self.status)
        box.addLayout(buttons)
        box.addWidget(self.log, 1)
        box.addWidget(line)
        box.addWidget(self.send_note)
        box.addLayout(send_row)
        self.resize(720, 520)
        self.show_steps(0)

    @staticmethod
    def row(edit, button):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit, 1)
        h.addWidget(button)
        return w

    def show_steps(self, current, failed=False, done=False):
        for i, l in enumerate(self.steps, 1):
            name = STEPS[i - 1]
            if done or i < current:
                l.setText("<span style='color:#2e9e5b'>✓</span> %s" % name)
            elif i == current:
                mark = "<span style='color:#c0392b'>✗</span>" if failed else "<b>▸</b>"
                l.setText("%s <b>%s</b> <span style='color:gray'>%s</span>" % (mark, name, "" if failed else ABOUT[i]))
            else:
                l.setText("<span style='color:gray'>○ %s</span>" % name)
        self.current = current

    def pick_game(self):
        start = os.path.dirname(self.game.text()) or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Your game file", start, "Game files (*.nup);;All files (*)")
        if path:
            self.game.setText(path)

    def pick_out(self):
        path = QFileDialog.getExistingDirectory(self, "Build into", self.out.text() or os.path.expanduser("~"))
        if path:
            self.out.setText(path)

    def busy(self, on):
        for w in (self.game, self.out, self.jobs):
            w.setEnabled(not on)
        self.go.setText("Stop" if on else "Build")

    def start_or_stop(self):
        if self.proc:
            if QMessageBox.question(self, "Stop the build?", "Stop the build? What it has done so far is kept: the next "
                                    "build goes on from there.") == QMessageBox.StandardButton.Yes and self.proc:
                self.stopping = True
                self.proc.kill()
            return
        game, out = self.game.text().strip(), self.out.text().strip()
        if not game or not os.path.exists(game):
            QMessageBox.warning(self, "No game file", "Choose your game file first: the .nup of your own copy of the game.")
            return
        if not out:
            QMessageBox.warning(self, "No folder", "Choose the folder to build into.")
            return
        for k, v in (("game", game), ("out", out), ("jobs", self.jobs.value())):
            self.settings.setValue(k, v)
        os.makedirs(out, exist_ok=True)
        self.log.clear()
        self.built = ""
        self.stopping = False
        self.pending = ""
        self.open.setEnabled(False)
        self.send.setEnabled(False)
        self.bar.setRange(0, 0)
        self.status.setText("Building…")
        self.show_steps(1)
        self.busy(True)
        args = ["-I", "-u", PIPELINE, "--game", game, "--out", out]
        if self.jobs.value():
            args += ["--jobs", str(self.jobs.value())]
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.proc_error)
        self.proc.start(sys.executable, args)

    def proc_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self.fail("The builder's own program did not start (%s)." % sys.executable)
            self.proc = None
            self.busy(False)

    def read(self):
        text = self.pending + bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        lines = text.split("\n")
        self.pending = lines.pop()
        for line in lines:
            self.line(line.rstrip("\r"))

    def line(self, line):
        if line.startswith("@@step "):
            n = int(line.split()[1])
            self.show_steps(n)
            self.bar.setRange(0, 0)
            self.status.setText(STEPS[n - 1] + "…")
        elif line.startswith("@@progress "):
            _, done, total = line.split()
            self.bar.setRange(0, int(total))
            self.bar.setValue(int(done))
            self.status.setText("%s: %s of %s files" % (STEPS[self.current - 1], done, total))
        elif line.startswith("@@done "):
            self.built = line[7:]
        elif line.startswith("@@error "):
            self.error = line[8:].replace(" | ", "\n")
        else:
            self.log.appendPlainText(line)

    def fail(self, text):
        self.show_steps(max(1, self.current), failed=True)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.status.setText(text.split("\n")[0])
        self.details.setChecked(True)
        self.log.appendPlainText("\n" + text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def finished(self, code, _status):
        if self.pending:
            self.line(self.pending)
        self.proc = None
        self.busy(False)
        if self.built and code == 0:
            self.show_steps(len(STEPS) + 1, done=True)
            self.bar.setRange(0, 1)
            self.bar.setValue(1)
            self.status.setText("Done. Your title folder: %s" % self.built)
            self.open.setEnabled(True)
            self.send.setEnabled(True)
        elif self.stopping:
            self.show_steps(self.current, failed=True)
            self.bar.setRange(0, 1)
            self.bar.setValue(0)
            self.status.setText("Stopped. Build again to go on from where it was.")
        else:
            self.fail(getattr(self, "error", "") or "The build stopped (exit %d). The details say where." % code)
        self.error = ""

    def start_send(self):
        host = self.ps5.text().strip()
        if not host:
            QMessageBox.warning(self, "No address", "Type the console's address: its IP on your network.")
            return
        self.settings.setValue("ps5", host)
        self.settings.setValue("port", self.port.value())
        self.send.setEnabled(False)
        self.go.setEnabled(False)
        self.status.setText("Sending to the console…")
        self.sender = Sender(self.built, host, self.port.value())
        self.sender.progress.connect(lambda a, b: (self.bar.setRange(0, b), self.bar.setValue(a)))
        self.sender.said.connect(self.log.appendPlainText)
        self.sender.ended.connect(self.sent)
        self.sender.start()

    def sent(self, error):
        self.send.setEnabled(True)
        self.go.setEnabled(True)
        if error:
            self.status.setText("Not sent: %s" % error)
            QMessageBox.warning(self, "Not sent", "The folder was not sent to the console.\n\n%s\n\nIs the console on, with its "
                                "FTP server running, at this address and port?" % error)
        else:
            self.status.setText("Sent: %s is in /data/homebrew on the console. Start Longshot from its home screen." %
                                os.path.basename(self.built))

    def closeEvent(self, e):
        if self.proc:
            if QMessageBox.question(self, "Stop the build?", "A build is running. Stop it and close?") != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.proc.kill()
            self.proc.waitForFinished(3000)
        e.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Longshot PS5 Builder")
    w = Window()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
