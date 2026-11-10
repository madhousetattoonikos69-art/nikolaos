import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading, asyncio, tempfile, subprocess, re, queue
APP="GreekDub AI"
def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
def srt_time(x):
    n=int(x*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,n=divmod(n,1000)
    return f"{h:02}:{m:02}:{s:02},{n:03}"
class Window:
    def __init__(self,root):
        self.root=root;root.title(APP);root.geometry("800x600")
        self.events=queue.Queue()
        root.after(100,self.drain_events)
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
        self.background=tk.BooleanVar(value=True)
        ttk.Checkbutton(root,text="Αρχικός ήχος χαμηλά (περιλαμβάνει και τις αρχικές φωνές)",variable=self.background).pack(anchor="w",padx=24,pady=5)
        self.btn=ttk.Button(root,text="Έναρξη ελληνικής μεταγλώττισης",command=self.start);self.btn.pack(pady=15)
        self.log=tk.Text(root,height=13,wrap="word");self.log.pack(fill="both",expand=True,padx=24,pady=12)
        self.say("Απαιτείται internet για την πρώτη λήψη μοντέλου, τη μετάφραση και τις ελληνικές φωνές.")
    def say(self,msg):self.events.put(("log",msg))
    def drain_events(self):
        try:
            while True:
                kind,msg=self.events.get_nowait()
                if kind=="log":
                    self.log.insert("end",msg+"\n");self.log.see("end")
                else:self.btn.configure(state="normal")
        except queue.Empty:pass
        self.root.after(100,self.drain_events)
    def pick(self):
        p=filedialog.askopenfilename(filetypes=[("Βίντεο","*.mp4 *.mkv *.mov *.avi *.webm")])
        if p:self.src.set(p)
    def pickdir(self):
        p=filedialog.askdirectory()
        if p:self.dest.set(p)
    def start(self):
        if not Path(self.src.get()).is_file():messagebox.showerror(APP,"Επίλεξε βίντεο.");return
        self.btn.configure(state="disabled")
        options=(self.src.get(),self.dest.get(),self.model.get(),self.background.get())
        threading.Thread(target=self.work,args=options,daemon=True).start()
    def work(self,*options):
        try:self.process(*options);self.say("Ολοκληρώθηκε!")
        except Exception as e:self.say("Σφάλμα: "+str(e))
        finally:self.events.put(("done",None))
    def process(self,source,destination,model_name,keep_background):
        from faster_whisper import WhisperModel
        from deep_translator import GoogleTranslator
        import edge_tts
        src=Path(source);out=Path(destination);out.mkdir(parents=True,exist_ok=True)
        self.say("Αναγνώριση ομιλίας...")
        segments,_=WhisperModel(model_name,device="cpu",compute_type="int8").transcribe(str(src),vad_filter=True)
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
            from datetime import datetime
            stem=re.sub(r"[^\w-]+","_",src.stem)[:75]+"_"+datetime.now().strftime("%Y%m%d_%H%M%S")
            (out/f"{stem}_el.srt").write_text("\n".join(subs),encoding="utf-8-sig")
            # Render each voice to a single timeline to avoid excessive FFmpeg inputs.
            # Original soundtrack is kept at low volume; original voices may remain audible.
            audio=td/"dub.wav"
            from pydub import AudioSegment
            AudioSegment.converter=ffmpeg()
            total=max(int(end*1000) for _,end,_ in segs)+3000
            track=AudioSegment.silent(duration=total,frame_rate=24000)
            for clip_index,(start,p) in enumerate(clips):
                # Decode with the bundled FFmpeg; pydub's MP3 reader otherwise needs ffprobe.
                decoded=td/"decoded.wav"
                proc=subprocess.run([ffmpeg(),"-nostdin","-y","-i",str(p),"-ac","1","-ar","24000",str(decoded)],
                                    capture_output=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                if proc.returncode:raise RuntimeError("Αποτυχία αποκωδικοποίησης ελληνικής φωνής.")
                clip=AudioSegment.from_wav(decoded)
                end=segs[clip_index][1]
                if clip_index+1<len(segs):end=min(end,segs[clip_index+1][0])
                available=max(1,int((end-start)*1000))
                if len(clip)>available:
                    ratio=len(clip)/available
                    filters=[]
                    while ratio>2:
                        filters.append("atempo=2");ratio/=2
                    filters.append(f"atempo={max(1,ratio):.8f}")
                    fitted=td/"fitted.wav"
                    fit=subprocess.run([ffmpeg(),"-nostdin","-y","-i",str(decoded),"-af",",".join(filters),
                                        "-t",str(available/1000),str(fitted)],capture_output=True,
                                        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                    if fit.returncode:raise RuntimeError("Αποτυχία συγχρονισμού ελληνικής φωνής.")
                    clip=AudioSegment.from_wav(fitted)[:available]
                track=track.overlay(clip,position=int(start*1000))
            track.export(audio,format="wav")
            target=out/f"{stem}_GreekDub.mp4"
            cmd=[ffmpeg(),"-y","-i",str(src),"-i",str(audio),"-filter_complex","[0:a]volume=0.10[bg];[bg][1:a]amix=inputs=2:duration=first[out]","-map","0:v:0","-map","[out]","-c:v","copy","-c:a","aac","-b:a","192k",str(target)]
            if not keep_background:
                filter_index=cmd.index("-filter_complex")
                del cmd[filter_index:filter_index+2]
                cmd[cmd.index("[out]")]="1:a:0"
            proc=subprocess.run(cmd,capture_output=True,text=True,errors="replace",creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if proc.returncode:
                self.say("Μετατροπή εικόνας σε συμβατή μορφή MP4...")
                video_index=cmd.index("-c:v")
                cmd[video_index:video_index+2]=["-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p"]
                proc=subprocess.run(cmd,capture_output=True,text=True,errors="replace",creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                if proc.returncode:raise RuntimeError(proc.stderr[-1600:])
            self.say("Αποθηκεύτηκε: "+str(target))
if __name__=="__main__":
    root=tk.Tk();Window(root);root.mainloop()
