import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading, asyncio, tempfile, subprocess, re
APP="GreekDub AI"
def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
def srt_time(x):
    n=int(x*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,n=divmod(n,1000)
    return f"{h:02}:{m:02}:{s:02},{n:03}"
class Window:
    def __init__(self,root):
        self.root=root;root.title(APP);root.geometry("760x540")
        self.src=tk.StringVar();self.dest=tk.StringVar(value=str(Path.home()/"Videos"/"GreekDubAI"))
        self.model=tk.StringVar(value="base")
        ttk.Label(root,text="GreekDub AI — Ελληνική μεταγλώττιση",font=("Segoe UI",18,"bold")).pack(pady=20)
        for title,var,callback in [("Επιλογή βίντεο",self.src,self.pick),("Φάκελος αποθήκευσης",self.dest,self.pickdir)]:
            ttk.Label(root,text=title).pack(anchor="w",padx=24)
            line=ttk.Frame(root);line.pack(fill="x",padx=24,pady=5)
            ttk.Entry(line,textvariable=var).pack(side="left",fill="x",expand=True)
            ttk.Button(line,text="Επιλογή",command=callback).pack(side="left")
        ttk.Label(root,text="Ποιότητα αναγνώρισης").pack(anchor="w",padx=24)
        ttk.Combobox(root,textvariable=self.model,values=["tiny","base","small","medium"],state="readonly").pack(anchor="w",padx=24)
        self.btn=ttk.Button(root,text="Έναρξη ελληνικής μεταγλώττισης",command=self.start);self.btn.pack(pady=15)
        self.log=tk.Text(root,height=13,wrap="word");self.log.pack(fill="both",expand=True,padx=24,pady=12)
        self.say("Απαιτείται internet για την πρώτη λήψη μοντέλου, τη μετάφραση και τις ελληνικές φωνές.")
    def say(self,msg):self.root.after(0,lambda:(self.log.insert("end",msg+"\n"),self.log.see("end")))
    def pick(self):
        p=filedialog.askopenfilename(filetypes=[("Βίντεο","*.mp4 *.mkv *.mov *.avi *.webm")])
        if p:self.src.set(p)
    def pickdir(self):
        p=filedialog.askdirectory()
        if p:self.dest.set(p)
    def start(self):
        if not Path(self.src.get()).is_file():messagebox.showerror(APP,"Επίλεξε βίντεο.");return
        self.btn.configure(state="disabled")
        threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:self.process();self.say("Ολοκληρώθηκε!")
        except Exception as e:self.say("Σφάλμα: "+str(e))
        finally:self.root.after(0,lambda:self.btn.configure(state="normal"))
    def process(self):
        from faster_whisper import WhisperModel
        from deep_translator import GoogleTranslator
        import edge_tts
        src=Path(self.src.get());out=Path(self.dest.get());out.mkdir(parents=True,exist_ok=True)
        self.say("Αναγνώριση ομιλίας...")
        segments,_=WhisperModel(self.model.get(),device="cpu",compute_type="int8").transcribe(str(src),vad_filter=True)
        segs=[(float(s.start),float(s.end),s.text.strip()) for s in segments if s.text.strip()]
        if not segs:raise RuntimeError("Δεν βρέθηκε ομιλία.")
        translator=GoogleTranslator(source="auto",target="el")
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);clips=[];subs=[]
            for i,(start,end,original) in enumerate(segs,1):
                translated=translator.translate(original) or original
                subs.append(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{translated}\n")
                p=td/f"{i:06}.mp3"
                asyncio.run(edge_tts.Communicate(translated,voice="el-GR-AthinaNeural").save(str(p)))
                clips.append((start,p))
                if i%10==0:self.say(f"Ελληνικές φωνές: {i}/{len(segs)}")
            stem=re.sub(r"[^\w-]+","_",src.stem)[:75]
            (out/f"{stem}_el.srt").write_text("\n".join(subs),encoding="utf-8-sig")
            # Render each voice to a single timeline to avoid excessive FFmpeg inputs.
            # Original soundtrack is kept at low volume; original voices may remain audible.
            audio=td/"dub.wav"
            from pydub import AudioSegment
            total=max(int(end*1000) for _,end,_ in segs)+3000
            track=AudioSegment.silent(duration=total)
            for start,p in clips:
                track=track.overlay(AudioSegment.from_file(p),position=int(start*1000))
            track.export(audio,format="wav")
            target=out/f"{stem}_GreekDub.mp4"
            cmd=[ffmpeg(),"-y","-i",str(src),"-i",str(audio),"-filter_complex","[0:a]volume=0.10[bg];[bg][1:a]amix=inputs=2:duration=first[out]","-map","0:v:0","-map","[out]","-c:v","copy","-c:a","aac","-b:a","192k",str(target)]
            proc=subprocess.run(cmd,capture_output=True,text=True,errors="replace")
            if proc.returncode:raise RuntimeError(proc.stderr[-1600:])
            self.say("Αποθηκεύτηκε: "+str(target))
if __name__=="__main__":
    root=tk.Tk();Window(root);root.mainloop()
