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
		colors: (!opts || !opts.colors) ? ["#71b32b", "#ed5a24"] : opts.colors,
		title: { text: null },
		legend: { enabled: false },
		series: [{
			type: "pie",
			data: [["Support", pro_pct], ["Oppose", con_pct]]
		}]
      });
   });
}

function two_part_bar_chart(container, pro_pct, con_pct, opts) {
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
			height:30,
        },
		colors: (!opts || !opts.colors) ? ["#ed5a24","#71b32b"] : opts.colors,
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
				size: (!opts || !opts.nopad) ? "75%" : "95%",
				groupPadding:0,
				pointPadding:0,
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
    		enabled: (!opts || opts.tooltip == null) ? true : opts.tooltip,
			formatter: function() {
					return this.series.name;
				},
		},
        series: [{
			name: opts.right_label,
            data: [con_pct]
        },{
			name: opts.left_label,
            data: [pro_pct]
        } ]

    });
/* end chart */

if (pro_pct == 0) {
	var chart_container = document.getElementById(container);
	if (document.implementation.hasFeature("http://www.w3.org/TR/SVG11/feature#BasicStructure", "1.1")) {
		var data_labels = chart_container.getElementsByClassName("highcharts-data-labels"); 
		var support_label = data_labels[1];
		var text_element = support_label.firstChild;
		var tspan = text_element.firstChild;
		text_element.removeChild(tspan);
	}
}
else if (pro_pct < 15) {
	var chart_container = document.getElementById(container);
	if (document.implementation.hasFeature("http://www.w3.org/TR/SVG11/feature#BasicStructure", "1.1")) {
		var data_labels = chart_container.getElementsByClassName("highcharts-data-labels");
		var oppose_label = data_labels[0];
		var text_element = oppose_label.firstChild;
		var tspan = text_element.firstChild;
		tspan.setAttribute("x","50");
	}
} else if (pro_pct == 100) {
	var chart_container = document.getElementById(container);
	if (document.implementation.hasFeature("http://www.w3.org/TR/SVG11/feature#BasicStructure", "1.1")) {
		var data_labels = chart_container.getElementsByClassName("highcharts-data-labels");
		var oppose_label = data_labels[0];
		var text_element = oppose_label.firstChild;
		var tspan = text_element.firstChild;
		text_element.removeChild(tspan);
		var support_label = data_labels[1];
		var text_element = support_label.firstChild;
		var tspan = text_element.firstChild;
		var width = parseInt(chart_container.offsetWidth);
		var newpoint = width - 5;
		text_element.setAttribute("text-anchor","end");
		tspan.setAttribute("x",newpoint);
	}
} else if (pro_pct > 85) {
	var chart_container = document.getElementById(container);
	if (document.implementation.hasFeature("http://www.w3.org/TR/SVG11/feature#BasicStructure", "1.1")) {
		var data_labels = chart_container.getElementsByClassName("highcharts-data-labels");
		var oppose_label = data_labels[0];
		var text_element = oppose_label.firstChild;
		var tspan = text_element.firstChild;
		var width = parseInt(chart_container.offsetWidth);
		var newpoint = width - 5;
		text_element.setAttribute("text-anchor","end");
		tspan.setAttribute("x",newpoint);
	}
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
	    width: (!opts || !opts.width) ? 220 : opts.width
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
	  colors: (!opts || !opts.colors) ? ["#71b32b", "#ed5a24"] : opts.colors,
      title: { text: null },
      legend: { enabled: false },
      series: [
	  { name: "Support", data: data.pro},
	  { name: "Oppose", data: data.con},
      ]
     });
   });
}



function race_chart(container, white, black, hispanic, asian, hpi, ai, biracial, other, opts) {
$(function () {
	new Highcharts.Chart({
        chart: {
            renderTo: container,
            type: 'pie',
            height:300,
            backgroundColor:"#D4D1CA",
			margin: [0,0,130,0],
			spacingTop: 0,
			spacingLeft: 0,
			spacingRight: 0,
			spacingBottom: 10
        },
        colors: ["#289DD3","#DE1969", "#FAF13C", "#A20089","#FD759B", "#3F4E75", "#BA5053","#FFFFFF"],
        credits: { enabled: false},
        title: {text: null},
		tooltip: {enabled: false},
        plotOptions: {
            series: {
                allowPointSelect: true
            },
            pie: {
                animation:false,
				borderWidth:0,
                innerSize:100,
                size:160,
				shadow:false,
                showInLegend:true,
                dataLabels: {
                    enabled: false,
                },
            }
        },
        legend: {
            labelFormatter: function() {
                return this.y+"% "+this.name
            },
            layout: 'vertical', 
            borderWidth:0,                            
			itemStyle: {textTransform: 'uppercase',
                    fontWeight:'bold',
					wordWrap: 'break-word'},
        },
        series: [{
            data: [['White', white],
                   ['Black',black], 
                   ['Hispanic',hispanic],
                   ['Asian', asian],
                   ['Native American',ai],
                   ['Pacific Islander',hpi],
                   ['Two or more',biracial],
                   ['Other',other]
                  ]
        }]
    });
});

}
