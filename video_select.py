import cv2
import tkinter as tk
from tkinter import filedialog
import json


class VideoPlayer:
    def __init__(self, master):
        self.photo = None
        self.master = master
        self.master.title("Video Player")
        self.filename = ""
        self.cap = None
        self.frame_idx = 0
        self.points = []

        # create a frame for the buttons
        self.button_frame = tk.Frame(self.master)
        self.button_frame.pack(side=tk.BOTTOM)

        # create buttons and pack them inside the button frame
        self.play_pause_button = tk.Button(self.button_frame, text="Play", command=self.toggle_play_pause,
                                           state=tk.DISABLED)
        self.play_pause_button.pack(side=tk.LEFT)
        self.select_button = tk.Button(self.button_frame, text="Select Video", command=self.select_video)
        self.select_button.pack(side=tk.LEFT)
        self.reset_button = tk.Button(self.button_frame, text="Reset", command=self.reset_points, state=tk.DISABLED)
        self.reset_button.pack(side=tk.LEFT)
        self.save_button = tk.Button(self.button_frame, text="Save", command=self.save_points, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self.master, width=640, height=480)
        self.canvas.pack()
        self.paused = True
        self.canvas.bind("<Button-1>", self.draw_point)
        self.canvas.bind("<Button-2>", self.reset_points)

    def select_video(self):
        self.filename = filedialog.askopenfilename(title="Select a video file",
                                                   filetypes=[("Video Files", "*.mp4 *.avi")])
        if self.filename:
            self.cap = cv2.VideoCapture(self.filename)
            self.frame_idx = 0
            self.play_pause_button.config(state=tk.NORMAL)

    def play_video(self):
        if self.filename:
            if not self.cap:
                self.cap = cv2.VideoCapture(self.filename)
            if not self.paused:
                ret, frame = self.cap.read()
                if ret:
                    if self.frame_idx == self.cap.get(cv2.CAP_PROP_FRAME_COUNT):
                        self.frame_idx = 0
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.photo = tk.PhotoImage(data=cv2.imencode(".png", frame)[1].tobytes())
                    self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
                    self.frame_idx += 1
                    self.master.after(1, self.play_video)

    def toggle_play_pause(self):
        if self.paused:
            self.play_pause_button.config(text="Pause")
            self.paused = False
            self.reset_button.config(state=tk.DISABLED)
            self.save_button.config(state=tk.DISABLED)
            self.play_video()
        else:
            self.play_pause_button.config(text="Play")
            if self.cap:
                self.cap.release()
                self.cap = None
            self.paused = True
            self.reset_button.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)

    def draw_point(self, event):
        if self.paused:
            if len(self.points) < 4:
                self.points.append([event.x, event.y])
                self.canvas.create_oval(event.x - 5, event.y - 5, event.x + 5, event.y + 5, fill="red", tags="point")
            else:
                self.reset_points()

    def reset_points(self):
        self.points = []
        self.canvas.delete("point")

    def save_points(self):
        if self.filename and self.points:
            # get current frame
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_idx - 1)
            ret, frame = self.cap.read()
            overlay = frame.copy()
            if not ret:
                return
            # draw points on frame
            for point in self.points:
                cv2.circle(frame, point, 3, (0, 0, 255), -1)

            # save image as png
            frame_filename = self.filename.split("/")[-1].split(".")[0] + f"_frame{self.frame_idx}.png"
            cv2.imwrite(frame_filename, frame)

            # save points as json
            points_dict = self.points
            points_filename = self.filename.split("/")[-1].split(".")[0] + f"_frame{self.frame_idx}.json"
            with open(points_filename, "w") as f:
                json.dump(points_dict, f)
            print("image saved")
        self.canvas.delete("all")


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoPlayer(root)
    root.mainloop()
