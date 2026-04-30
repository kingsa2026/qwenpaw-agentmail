/**
 * AgentMail Plugin - 前端入口 (JavaScript 版本)
 * 
 * 注册侧边栏菜单和页面路由，使用 QwenPaw 原生 UI 组件
 */

(function() {
  'use strict';

  // 检查 QwenPaw 环境
  if (!window.QwenPaw) {
    console.error('[agentmail] QwenPaw 环境未找到');
    return;
  }

  if (!window.QwenPaw.host) {
    console.error('[agentmail] QwenPaw.host 未找到');
    return;
  }

  // 获取共享依赖
  var host = window.QwenPaw.host;
  var React = host.React;
  var antd = host.antd;
  var icons = host.icons;

  if (!React || !antd) {
    console.error('[agentmail] React 或 antd 未找到');
    return;
  }

  // 解构组件
  var Card = antd.Card;
  var Button = antd.Button;
  var Tabs = antd.Tabs;
  var Table = antd.Table;
  var Badge = antd.Badge;
  var Space = antd.Space;
  var Tag = antd.Tag;
  var Typography = antd.Typography;
  var Empty = antd.Empty;
  var Alert = antd.Alert;

  // 解构图标
  var MailOutlined = icons.MailOutlined;
  var InboxOutlined = icons.InboxOutlined;
  var SendOutlined = icons.SendOutlined;
  var EditOutlined = icons.EditOutlined;
  var SettingOutlined = icons.SettingOutlined;
  var ReloadOutlined = icons.ReloadOutlined;
  var PlusOutlined = icons.PlusOutlined;

  var Title = Typography.Title;
  var Text = Typography.Text;

  // 错误边界组件
  function ErrorBoundary(props) {
    var _React$useState = React.useState(false);
    var hasError = _React$useState[0];
    var setHasError = _React$useState[1];

    var _React$useState2 = React.useState(null);
    var error = _React$useState2[0];
    var setError = _React$useState2[1];

    React.useEffect(function() {
      if (props.error) {
        setHasError(true);
        setError(props.error);
      }
    }, [props.error]);

    if (hasError) {
      return React.createElement(Alert, {
        message: "插件加载错误",
        description: error ? error.message : "未知错误",
        type: "error",
        showIcon: true
      });
    }

    return props.children;
  }

  // 邮件管理页面
  function EmailPage() {
    var _React$useState3 = React.useState("inbox");
    var activeTab = _React$useState3[0];
    var setActiveTab = _React$useState3[1];

    var _React$useState4 = React.useState(false);
    var loading = _React$useState4[0];
    var setLoading = _React$useState4[1];

    var _React$useState5 = React.useState([]);
    var emails = _React$useState5[0];
    var setEmails = _React$useState5[1];

    // 加载邮件数据
    React.useEffect(function() {
      // 模拟加载数据
      var mockEmails = [
        {
          id: "1",
          subject: "欢迎使用 AgentMail",
          sender: "system@qwenpaw.ai",
          date: "2024-01-01",
          read: false,
          folder: "inbox"
        }
      ];
      setEmails(mockEmails);
    }, []);

    // 表格列定义
    var columns = [
      {
        title: "状态",
        dataIndex: "read",
        key: "read",
        width: 80,
        render: function(read) {
          return React.createElement(Badge, { 
            status: read ? "default" : "processing",
            text: read ? "已读" : "未读"
          });
        }
      },
      {
        title: "主题",
        dataIndex: "subject",
        key: "subject",
        ellipsis: true
      },
      {
        title: "发件人",
        dataIndex: "sender",
        key: "sender",
        width: 200
      },
      {
        title: "日期",
        dataIndex: "date",
        key: "date",
        width: 150
      },
      {
        title: "操作",
        key: "action",
        width: 150,
        render: function(_, record) {
          return React.createElement(Space, { size: "middle" },
            React.createElement(Button, { 
              type: "link", 
              size: "small",
              onClick: function() { 
                console.log("查看邮件:", record.id); 
              }
            }, "查看"),
            React.createElement(Button, { 
              type: "link", 
              danger: true,
              size: "small",
              onClick: function() { 
                console.log("删除邮件:", record.id); 
              }
            }, "删除")
          );
        }
      }
    ];

    // 收件箱标签页
    function InboxTab() {
      return React.createElement("div", null,
        React.createElement("div", { 
          style: { marginBottom: 16, display: "flex", justifyContent: "space-between" } 
        },
          React.createElement(Space, null,
            React.createElement(Button, { 
              type: "primary",
              icon: React.createElement(ReloadOutlined),
              loading: loading,
              onClick: function() {
                setLoading(true);
                setTimeout(function() { 
                  setLoading(false); 
                }, 1000);
              }
            }, "刷新"),
            React.createElement(Button, { 
              icon: React.createElement(EditOutlined),
              onClick: function() { 
                console.log("写邮件"); 
              }
            }, "写邮件")
          ),
          React.createElement(Button, { 
            onClick: function() { 
              console.log("标记全部已读"); 
            }
          }, "标记全部已读")
        ),
        React.createElement(Table, {
          columns: columns,
          dataSource: emails,
          rowKey: "id",
          locale: { 
            emptyText: React.createElement(Empty, { description: "暂无邮件" }) 
          }
        })
      );
    }

    // 已发送标签页
    function SentTab() {
      return React.createElement("div", null,
        React.createElement("div", { style: { marginBottom: 16 } },
          React.createElement(Button, { 
            type: "primary",
            icon: React.createElement(PlusOutlined),
            onClick: function() { 
              console.log("写邮件"); 
            }
          }, "写邮件")
        ),
        React.createElement(Empty, { description: "暂无已发送邮件" })
      );
    }

    // 草稿箱标签页
    function DraftsTab() {
      return React.createElement("div", null,
        React.createElement("div", { style: { marginBottom: 16 } },
          React.createElement(Button, { 
            type: "primary",
            icon: React.createElement(PlusOutlined),
            onClick: function() { 
              console.log("写邮件"); 
            }
          }, "写邮件")
        ),
        React.createElement(Empty, { description: "暂无草稿" })
      );
    }

    // 配置标签页
    function ConfigTab() {
      return React.createElement("div", null,
        React.createElement(Card, { 
          title: "邮箱配置", 
          style: { marginBottom: 16 } 
        },
          React.createElement("p", null, "选择邮箱类型："),
          React.createElement("div", { 
            style: { display: "flex", gap: 16, marginTop: 16 } 
          },
            React.createElement(Card, {
              hoverable: true,
              style: { width: 200, textAlign: "center", cursor: "pointer" },
              onClick: function() { 
                console.log("传统邮箱配置"); 
              }
            },
              React.createElement("div", { style: { fontSize: 32 } }, "📮"),
              React.createElement("p", { style: { marginTop: 8 } }, "传统邮箱"),
              React.createElement(Text, { 
                type: "secondary", 
                style: { fontSize: 12 } 
              }, "POP3/IMAP/SMTP")
            ),
            React.createElement(Card, {
              hoverable: true,
              style: { width: 200, textAlign: "center", cursor: "pointer" },
              onClick: function() { 
                console.log("AgentMail.to 配置"); 
              }
            },
              React.createElement("div", { style: { fontSize: 32 } }, "🤖"),
              React.createElement("p", { style: { marginTop: 8 } }, "AgentMail.to"),
              React.createElement(Text, { 
                type: "secondary", 
                style: { fontSize: 12 } 
              }, "AI 专用邮箱")
            ),
            React.createElement(Card, {
              hoverable: true,
              style: { width: 200, textAlign: "center", cursor: "pointer" },
              onClick: function() { 
                console.log("混合模式配置"); 
              }
            },
              React.createElement("div", { style: { fontSize: 32 } }, "🔀"),
              React.createElement("p", { style: { marginTop: 8 } }, "混合模式"),
              React.createElement(Text, { 
                type: "secondary", 
                style: { fontSize: 12 } 
              }, "传统 + AgentMail")
            )
          )
        ),
        React.createElement(Card, { title: "当前配置" },
          React.createElement("p", null, 
            "模式: ", 
            React.createElement(Tag, { color: "blue" }, "未配置")
          ),
          React.createElement("p", null, 
            "邮箱: ", 
            React.createElement(Text, { type: "secondary" }, "--")
          ),
          React.createElement("p", null, 
            "状态: ", 
            React.createElement(Badge, { 
              status: "default", 
              text: "未连接" 
            })
          )
        )
      );
    }

    return React.createElement(ErrorBoundary, null,
      React.createElement("div", { style: { padding: "24px" } },
        React.createElement(Title, { 
          level: 2, 
          style: { marginBottom: 24 } 
        }, 
          React.createElement(MailOutlined, { style: { marginRight: 8 } }),
          "邮件管理"
        ),
        React.createElement(Card, null,
          React.createElement(Tabs, {
            activeKey: activeTab,
            onChange: setActiveTab,
            items: [
              {
                key: "inbox",
                label: React.createElement("span", null, 
                  React.createElement(InboxOutlined, { style: { marginRight: 4 } }),
                  "收件箱"
                ),
                children: React.createElement(InboxTab)
              },
              {
                key: "sent",
                label: React.createElement("span", null, 
                  React.createElement(SendOutlined, { style: { marginRight: 4 } }),
                  "已发送"
                ),
                children: React.createElement(SentTab)
              },
              {
                key: "drafts",
                label: React.createElement("span", null, 
                  React.createElement(EditOutlined, { style: { marginRight: 4 } }),
                  "草稿箱"
                ),
                children: React.createElement(DraftsTab)
              },
              {
                key: "config",
                label: React.createElement("span", null, 
                  React.createElement(SettingOutlined, { style: { marginRight: 4 } }),
                  "邮箱配置"
                ),
                children: React.createElement(ConfigTab)
              }
            ]
          })
        )
      )
    );
  }

  // 插件 ID
  var PLUGIN_ID = "agentmail";

  // 注册路由
  function registerPlugin() {
    try {
      if (window.QwenPaw && window.QwenPaw.registerRoutes) {
        window.QwenPaw.registerRoutes(PLUGIN_ID, [
          {
            path: "/email",
            component: EmailPage,
            label: "邮件管理",
            icon: "MailOutlined",
            priority: 10
          }
        ]);
        console.info('[' + PLUGIN_ID + '] ✓ 侧边栏路由已注册');
      } else {
        console.error('[' + PLUGIN_ID + '] ✗ window.QwenPaw.registerRoutes 不可用');
      }
    } catch (error) {
      console.error('[' + PLUGIN_ID + '] ✗ 注册失败:', error);
    }
  }

  // 延迟注册，确保 QwenPaw 已准备好
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', registerPlugin);
  } else {
    registerPlugin();
  }

  // 导出到全局
  window.AgentMailPlugin = {
    EmailPage: EmailPage,
    version: "1.0.0"
  };

})();
