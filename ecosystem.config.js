module.exports = {
  apps : [{
          name: "webhook",
          script: "/usr/bin/webhook",
          cwd: "/opt/undp_png",
          args: "-hooks hooks.json -verbose",
          env: {
            "MACHINE": "development"
          },
         env_production: {
            "MACHINE": "production",
         }
  }]
};
