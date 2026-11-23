import {ref,onMounted,onBeforeUnmount} from 'vue';

export function resolveSystemTheme(doc, win) {
    for (const element of [doc?.documentElement, doc?.body]) {
        const value=element?.getAttribute?.('data-theme')?.toLowerCase();
        if(value==='dark' || value==='light')return value==='dark' ? 'Dark' : 'Light';
    }
    for(const element of [doc?.documentElement,doc?.body]){
        const classes=element?.classList;
        if(classes?.contains('dark'))return 'Dark';
        if(classes?.contains('light'))return 'Light';
    }
    return win?.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'Dark' : 'Light';
}

export function useSystemTheme() {
    const doc=typeof document==='undefined' ? null : document;
    const win=typeof window==='undefined' ? null : window;
    const theme=ref(resolveSystemTheme(doc,win));
    let observer=null,media=null;
    const refresh=()=>{theme.value=resolveSystemTheme(doc,win);};
    onMounted(()=>{
        refresh();
        if(typeof MutationObserver!=='undefined' && doc?.documentElement){
            observer=new MutationObserver(refresh);
            observer.observe(doc.documentElement,{attributes:true,attributeFilter:['data-theme','class']});
            if(doc.body)observer.observe(doc.body,{attributes:true,attributeFilter:['data-theme','class']});
        }
        media=win?.matchMedia?.('(prefers-color-scheme: dark)');
        if(media?.addEventListener)media.addEventListener('change',refresh);
        else media?.addListener?.(refresh);
    });
    onBeforeUnmount(()=>{
        observer?.disconnect();
        if(media?.removeEventListener)media.removeEventListener('change',refresh);
        else media?.removeListener?.(refresh);
    });
    return theme;
}
