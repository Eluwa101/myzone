import { forwardRef, useImperativeHandle, useRef } from "react";
import ReactQuill from "react-quill-new";
import "react-quill-new/dist/quill.snow.css";

export interface RichTextEditorHandle {
  insertTextAtCursor: (text: string) => void;
}

const TOOLBAR_MODULES = {
  toolbar: [
    [{ header: [false, 1, 2] }],
    ["bold", "italic", "underline"],
    [{ color: [] }, { background: [] }],
    [{ align: [] }],
    [{ list: "ordered" }, { list: "bullet" }],
    ["link", "image"],
    ["clean"],
  ],
};

/** Lightweight rich-text compose surface (colors, headings, alignment,
 * images, links) - imperatively exposes insertTextAtCursor so the merge-tag
 * picker can drop a {{tag}} wherever the cursor currently is, rather than
 * always appending to the end. */
const RichTextEditor = forwardRef<RichTextEditorHandle, { value: string; onChange: (html: string) => void; placeholder?: string }>(
  ({ value, onChange, placeholder }, ref) => {
    const quillRef = useRef<ReactQuill>(null);

    useImperativeHandle(ref, () => ({
      insertTextAtCursor(text: string) {
        const editor = quillRef.current?.getEditor();
        if (!editor) return;
        const range = editor.getSelection(true);
        const index = range ? range.index : editor.getLength();
        editor.insertText(index, text, "user");
        editor.setSelection(index + text.length, 0);
      },
    }));

    return (
      <ReactQuill ref={quillRef} theme="snow" value={value} onChange={onChange} modules={TOOLBAR_MODULES} placeholder={placeholder} />
    );
  }
);

RichTextEditor.displayName = "RichTextEditor";

export default RichTextEditor;
