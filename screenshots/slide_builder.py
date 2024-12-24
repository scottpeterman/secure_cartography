import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import simpledialog
from PIL import Image, ImageTk
import os


class GifMakerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNG to Animated GIF Converter")
        self.geometry("600x400")
        self.image_list = []
        self.delay = 1000
        self.bg_color = (255, 255, 255)  # Default white background

        # Color picker frame
        self.color_frame = tk.Frame(self)
        self.color_frame.pack(pady=5)

        tk.Label(self.color_frame, text="Background:").pack(side=tk.LEFT)
        self.color_buttons = []
        colors = ['white', 'black', 'blue', 'red', 'green', 'gray']

        for color in colors:
            btn = tk.Button(self.color_frame, width=2, bg=color,
                            command=lambda c=color: self.set_bg_color(c))
            btn.pack(side=tk.LEFT, padx=2)
            self.color_buttons.append(btn)

        # Main frame for listbox
        self.frame = tk.Frame(self)
        self.frame.pack(pady=10)

        self.listbox = tk.Listbox(self.frame, width=50, height=15)
        self.listbox.pack(side=tk.LEFT, padx=10)

        self.scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=self.scrollbar.set)

        # Control buttons
        self.add_button = tk.Button(self, text="Add PNG Files", command=self.add_files)
        self.add_button.pack(pady=5)

        self.remove_button = tk.Button(self, text="Remove Selected", command=self.remove_selected)
        self.remove_button.pack(pady=5)

        self.move_up_button = tk.Button(self, text="Move Up", command=self.move_up)
        self.move_up_button.pack(pady=5)

        self.move_down_button = tk.Button(self, text="Move Down", command=self.move_down)
        self.move_down_button.pack(pady=5)

        self.set_delay_button = tk.Button(self, text="Set Delay (ms)", command=self.set_delay)
        self.set_delay_button.pack(pady=5)

        self.convert_button = tk.Button(self, text="Convert to GIF", command=self.convert_to_gif)
        self.convert_button.pack(pady=5)

    def set_bg_color(self, color):
        try:
            color_map = {
                'white': (255, 255, 255),
                'black': (0, 0, 0),
                'blue': (0, 0, 255),
                'red': (255, 0, 0),
                'green': (0, 255, 0),
                'gray': (128, 128, 128)
            }
            self.bg_color = color_map[color]
            for btn in self.color_buttons:
                btn.config(relief='raised')
            self.color_buttons[list(color_map.keys()).index(color)].config(relief='sunken')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set background color: {str(e)}")

    def normalize_images(self, images):
        try:
            # Find maximum dimensions
            max_width = max(img.size[0] for img in images)
            max_height = max(img.size[1] for img in images)

            normalized_images = []
            for img in images:
                # Calculate scaling factor while maintaining aspect ratio
                width_ratio = max_width / img.size[0]
                height_ratio = max_height / img.size[1]
                scale_factor = min(width_ratio, height_ratio)

                # Scale the image
                new_width = int(img.size[0] * scale_factor)
                new_height = int(img.size[1] * scale_factor)
                scaled_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Create new image with max dimensions and background color
                new_img = Image.new('RGB', (max_width, max_height), self.bg_color)

                # Calculate position to center the scaled image
                left = (max_width - new_width) // 2
                top = (max_height - new_height) // 2

                # Paste the scaled image onto the new background
                new_img.paste(scaled_img, (left, top))
                normalized_images.append(new_img)

            return normalized_images
        except Exception as e:
            messagebox.showerror("Error", f"Failed to normalize images: {str(e)}")
            return None

    def add_files(self):
        try:
            files = filedialog.askopenfilenames(filetypes=[("PNG files", "*.png")])
            for file in files:
                if file not in self.image_list:
                    self.image_list.append(file)
                    self.listbox.insert(tk.END, os.path.basename(file))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add files: {str(e)}")

    def remove_selected(self):
        try:
            selected = self.listbox.curselection()
            if not selected:
                messagebox.showwarning("Warning", "No item selected.")
                return
            index = selected[0]
            self.image_list.pop(index)
            self.listbox.delete(index)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove file: {str(e)}")

    def move_up(self):
        try:
            selected = self.listbox.curselection()
            if not selected or selected[0] == 0:
                return
            index = selected[0]
            self.image_list[index], self.image_list[index - 1] = self.image_list[index - 1], self.image_list[index]
            self.update_listbox()
            self.listbox.selection_set(index - 1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to move item: {str(e)}")

    def move_down(self):
        try:
            selected = self.listbox.curselection()
            if not selected or selected[0] == len(self.image_list) - 1:
                return
            index = selected[0]
            self.image_list[index], self.image_list[index + 1] = self.image_list[index + 1], self.image_list[index]
            self.update_listbox()
            self.listbox.selection_set(index + 1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to move item: {str(e)}")

    def set_delay(self):
        try:
            delay = simpledialog.askinteger("Set Delay", "Enter delay between frames (ms):",
                                            minvalue=100, maxvalue=10000)
            if delay:
                self.delay = delay
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set delay: {str(e)}")

    def update_listbox(self):
        try:
            self.listbox.delete(0, tk.END)
            for file in self.image_list:
                self.listbox.insert(tk.END, os.path.basename(file))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update list: {str(e)}")

    def convert_to_gif(self):
        if not self.image_list:
            messagebox.showwarning("Warning", "No images selected.")
            return

        try:
            output_file = filedialog.asksaveasfilename(defaultextension=".gif",
                                                       filetypes=[("GIF files", "*.gif")])
            if not output_file:
                return

            # Load and normalize images
            original_images = []
            for file in self.image_list:
                img = Image.open(file)
                img = img.convert('RGB')  # Convert to RGB immediately
                original_images.append(img)

            normalized_images = self.normalize_images(original_images)
            if not normalized_images:
                return

            # Save as animated GIF
            normalized_images[0].save(
                output_file,
                save_all=True,
                append_images=normalized_images[1:],
                duration=self.delay,
                loop=0,
                optimize=False
            )

            messagebox.showinfo("Success", f"GIF saved as {output_file}")
            self.preview_gif(output_file)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create GIF: {str(e)}")

    def preview_gif(self, gif_file):
        preview = None
        try:
            preview = tk.Toplevel(self)
            preview.title("GIF Preview")

            img = Image.open(gif_file)
            frames = []

            current_frame = 0
            while True:
                try:
                    img.seek(current_frame)
                    copy = img.copy()
                    frames.append(ImageTk.PhotoImage(copy))
                    current_frame += 1
                except EOFError:
                    break

            if not frames:
                messagebox.showerror("Error", "No frames found in GIF")
                if preview:
                    preview.destroy()
                return

            label = tk.Label(preview)
            label.pack()

            def animate(index=0):
                if not preview.winfo_exists():
                    return
                try:
                    label.config(image=frames[index])
                    preview.after(self.delay, animate, (index + 1) % len(frames))
                except tk.TclError:
                    return  # Window was closed

            animate()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview GIF: {str(e)}")
            if preview and preview.winfo_exists():
                preview.destroy()


if __name__ == "__main__":
    app = GifMakerApp()
    app.mainloop()