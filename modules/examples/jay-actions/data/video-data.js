// Data for the Jay action demo. Built by tools/build-data.mjs; times are video seconds.
window.VIDEO = {
  captions: [
    {"start":0.6,"end":3.95,"text":"wave · 挥手 — 开场欢迎、结尾告别"},
    {"start":4.5,"end":6.35,"text":"nod · 点头 — 确认、讲完一个要点"},
    {"start":6.9,"end":8.25,"text":"nod-small · 小点头 — 边讲边认同"},
    {"start":8.8,"end":10.75,"text":"shake · 摇头 — 否定、不推荐"},
    {"start":11.3,"end":13.65,"text":"tilt · 歪头好奇 — 提出问题"},
    {"start":14.2,"end":16.95,"text":"question · 疑问（?） — 抛出问题"},
    {"start":17.5,"end":19.65,"text":"startle · 惊讶后仰 — 意外的信息"},
    {"start":20.2,"end":23.25,"text":"eureka · 惊喜（!） — 亮出关键数字"},
    {"start":23.8,"end":26.55,"text":"idea · 灵感（灯泡） — 关键思路"},
    {"start":27.1,"end":29.65,"text":"smile · 微笑（嘴角上扬） — 温和的认可"},
    {"start":30.2,"end":32.75,"text":"laugh · 大笑（嘴角上扬、张嘴） — 轻松的点评"},
    {"start":33.3,"end":36.05,"text":"think · 思考（气泡） — 讲注意事项"},
    {"start":36.6,"end":39.55,"text":"sigh · 叹气 — 遗憾、限制条件"},
    {"start":40.1,"end":42.85,"text":"lean · 凑近看 — 仔细看这里（配合看向左边）"},
    {"start":43.4,"end":46.15,"text":"doubletake · 回头再看 — 反转、意外的细节"},
    {"start":46.7,"end":49.45,"text":"typing · 打字 — 换章节前"},
    {"start":50,"end":51.85,"text":"glance L · 看左边（主展示区）"},
    {"start":52.4,"end":54.25,"text":"glance U · 看上方（副展示区）"},
    {"start":54.8,"end":56.65,"text":"glance R · 看右边"},
    {"start":57.2,"end":59.05,"text":"glance D · 低头看笔记本"}
  ],
  jay: {
    acts: [[0.6,"wave",3000],[4.5,"nod",1500],[6.9,"nod-small",1000],[8.8,"shake",1600],[11.3,"tilt",2000],[14.2,"question",2400],[17.5,"startle",1800],[20.2,"eureka",2700],[23.8,"idea",2400],[27.1,"smile",2200],[30.2,"laugh",2200],[33.3,"think",2400],[36.6,"sigh",2600],[40.1,"lean",2400],[43.4,"doubletake",2400]],
    thoughts: [[33.3,"这是什么？"]],
    typing: [[46.7,49.1]],
    glances: [[40.1,2.4,"L"],[50,1.5,"L"],[52.4,1.5,"U"],[54.8,1.5,"R"],[57.2,1.5,"D"]],
    envelopeFps: 30,
    envelope: [],
  },
};
