function s(i,e,o,t,n){e.set(!0),i.subscribe({next:r=>{e.set(!1),o.success(t),n(r)},error:r=>{e.set(!1),o.error(r)}})}export{s as a};
