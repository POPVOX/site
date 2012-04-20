function bill_chart(container, pro_pct, con_pct, opts) {
	$(function() {
      new Highcharts.Chart({
		chart: {
			backgroundColor: (!opts || !opts.bg) ? "#e8e5df" : opts.bg,
			renderTo: container,
			margin: [0,0,0,0],
			spacingTop: 0,
			spacingLeft: 0,
			spacingRight: 0,
			spacingBottom: 0
		},
		tooltip: {
			enabled: false, //opts && opts.small,
			formatter: function() {
				return this.point.name + "<br>" + this.y + "%";
			}
		},
		credits: { enabled: false },
		plotOptions: {
			pie: {
				animation: false,
				//enableMouseTracking: false,
				stickyTracking: false,
				shadow: false,
				//borderColor: "#8BB6D9",
				borderWidth: 0,
				innerSize: (!opts || !opts.nopad) ? "40%" : "50%",
				size: (!opts || !opts.nopad) ? "75%" : "95%",
				dataLabels: {
					enabled: (opts && opts.labels ? true : false),
					distance: -30,
					formatter: function() {
						return this.point.name + "<br>" + this.y + "%";
					},
					color: 'white',
					style: {
						font: 'bold 14px Verdana, sans-serif'
					}
				}
			}
		},
		colors: ["#71b32b", "#ed5a24"],
		title: { text: null },
		legend: { enabled: false },
		series: [{
			type: "pie",
			data: [["Support", pro_pct], ["Oppose", con_pct]]
		}]
      });
   });
}

function bill_bar_chart(container, pro_pct, con_pct, opts) {
$(function () {
    new Highcharts.Chart({
        chart: {
            renderTo: container,
            type: 'bar',
			margin: [0,0,0,0],
			spacingTop: 0,
			spacingLeft: 0,
			spacingRight: 0,
			spacingBottom: 0,
			height:75,
        },
        colors: ["#ed5a24","#71b32b"],
        title: { text: null },
		credits: { enabled: false },
        legend: {
            enabled:false
        },
        xAxis: {
            labels: {
                enabled: false
            },
            lineWidth:0,
            gridLineWidth:0,
        },
        yAxis: {
            labels: {
                enabled: false,
            },
            title: {
                text:"",
            },
            stackLabels: {
                enabled: false,
                
            },
            lineWidth:0,
            gridLineWidth:0,
        },
        plotOptions: {
            bar: {
				animation: false,
				stickyTracking: false,
				borderWidth: 0,
				shadow: false,
                stacking: 'percent',
                dataLabels:{
                    enabled:true,
                    color:"#FFFFFF",
                    style: {
                        fontWeight:'bold',
                        align:"center"
                    },
					formatter: function() {
						return this.y + "%";
					},
                },                    
            }
        },
        tooltip: {
			enabled: false,
		},
        series: [{
            name: "Oppose",
            data: [con_pct]
        },{
            name: "Support",
            data: [pro_pct]
        } ]

    });
/* end chart */

if (pro_pct == 0) {
	var chart_container = document.getElementById(container);
	var data_labels = chart_container.getElementsByClassName("highcharts-data-labels");
	var support_label = data_labels[1];
	var text_element = support_label.firstChild;
	var tspan = text_element.firstChild;
	text_element.removeChild(tspan);
}
else if (pro_pct < 15) {
	var chart_container = document.getElementById(container);
	var data_labels = chart_container.getElementsByClassName("highcharts-data-labels");
	var oppose_label = data_labels[0];
	var text_element = oppose_label.firstChild;
	var tspan = text_element.firstChild;
	tspan.setAttribute("x","50");
}

}
);
}

function bill_timeseries(container, data, opts) {
	$(function() {
      new Highcharts.Chart({
	 chart: {
	 	backgroundColor: (!opts || !opts.bg) ? "#e8e5df" : opts.bg,
	    renderTo: container,
	    margin: [10,0,(!opts || !opts.xlabels) ? 10 : 65, 70],
	    defaultSeriesType: 'line',
	    width: (!opts || !opts.xlabels) ? 220 : opts.width
	 },
    tooltip: {
    	enabled: (!opts || opts.tooltip == null) ? true : opts.tooltip,
	    formatter: function() {
		    return this.x + ": " + this.y + " " + this.series.name
		}
    },
	 credits: { enabled: false },
	 xAxis: { categories: data.xaxis, labels: { enabled: (!opts || !opts.xlabels) ? false : opts.xlabels, step: 5, rotation: -70, y: 25 } },
	 yAxis: { min: 0, title: { text: "Cumulative Users", style: { fontSize: "10px", fontWeight: "normal" } } },
	 plotOptions: {
		    line: {
		       //enableMouseTracking: false,
			  marker: {
				  enabled: false
			  },
			  stickyTracking: false,
			  dataLabels: {
				enabled: false
			  }
		    }
	    },
		colors: ["#71b32b", "#ed5a24"],
      title: { text: null },
      legend: { enabled: false },
      series: [
	  { name: "Support", data: data.pro},
	  { name: "Oppose", data: data.con},
      ]
     });
   });
}

